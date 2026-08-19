"""
Marqueurs invisibles posés dans le document généré.

Deux niveaux, et un principe : **le script est propriétaire de ses données,
l'utilisateur du reste.**

    pbi::elem|<identifiant>|<empreinte>   ancre un élément documenté
    pbi::gen|<bloc>  ...  pbi::endgen     encadrent un contenu produit par le script

Tout ce qui se trouve entre deux ancres sans être encadré par `gen` appartient
à l'utilisateur : titre reformulé, note ajoutée, capture collée, mise en forme.
À la régénération, seuls les contenus `gen` sont réécrits ; le reste est
recopié tel quel.

Les marqueurs occupent un paragraphe dont le texte porte l'attribut Word
« masqué » (`w:vanish`) : Word ne l'affiche ni ne l'imprime, et le paragraphe
ne prend aucune place tant que l'affichage du texte masqué est désactivé.
"""

import hashlib
from dataclasses import dataclass

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

PREFIX = "pbi::"

ELEMENT = "elem"
GENERATED = "gen"
GENERATED_END = "endgen"

# Séparateur des champs. Les identifiants d'éléments contiennent des « : »
# (`measure:Chiffre d'affaires`) mais jamais de barre verticale.
_SEPARATOR = "|"

_FINGERPRINT_LENGTH = 10

_TEXT = qn("w:t")


@dataclass(frozen=True)
class Marker:
    """Marqueur reconnu dans un document."""

    kind: str  # "elem", "gen" ou "endgen"
    value: str = ""  # identifiant d'élément, ou identifiant de bloc du plan
    fingerprint: str = ""


# ─────────────────────────────────────────────────────────────
#  Écriture
# ─────────────────────────────────────────────────────────────


def element(element_id: str, fingerprint: str) -> str:
    return f"{PREFIX}{ELEMENT}{_SEPARATOR}{element_id}{_SEPARATOR}{fingerprint}"


def generated(block_id: str) -> str:
    return f"{PREFIX}{GENERATED}{_SEPARATOR}{block_id}"


def generated_end() -> str:
    return f"{PREFIX}{GENERATED_END}"


def fingerprint(text: str) -> str:
    """
    Empreinte du contenu technique d'un élément (expression DAX, champs d'un
    visuel...). Une empreinte plutôt que le texte lui-même : le marqueur reste
    court et ne recopie pas le contenu du document dans du texte masqué.
    """
    normalized = " ".join((text or "").split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]


def write(doc, text: str) -> None:
    """Ajoute au document un paragraphe masqué portant le marqueur."""
    paragraph = doc.add_paragraph()
    hide(paragraph.add_run(text))


def hide(run) -> None:
    """Applique l'attribut « masqué » à un run."""
    properties = run._r.get_or_add_rPr()
    if properties.find(qn("w:vanish")) is None:
        properties.append(OxmlElement("w:vanish"))


# ─────────────────────────────────────────────────────────────
#  Lecture
# ─────────────────────────────────────────────────────────────


def parse(text: str) -> Marker | None:
    """Reconnaît un marqueur dans le texte d'un paragraphe, sinon None."""
    text = (text or "").strip()
    if not text.startswith(PREFIX):
        return None

    kind, _, rest = text[len(PREFIX) :].partition(_SEPARATOR)

    if kind == GENERATED_END:
        return Marker(kind=GENERATED_END)
    if kind == GENERATED and rest:
        return Marker(kind=GENERATED, value=rest)
    if kind == ELEMENT and _SEPARATOR in rest:
        value, _, digest = rest.rpartition(_SEPARATOR)
        return Marker(kind=ELEMENT, value=value, fingerprint=digest)
    return None


def of(node) -> Marker | None:
    """Marqueur porté par un élément XML de corps de document (`w:p`), sinon None."""
    if node.tag != qn("w:p"):
        return None
    return parse("".join(text.text or "" for text in node.iter(_TEXT)))
