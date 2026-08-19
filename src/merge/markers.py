"""
Marqueurs invisibles posés dans le document généré.

Ils sont ce qui permet de retrouver, lors d'une regénération, quel passage du
document correspond à quel élément du rapport Power BI :

    pbi::elem|<identifiant>|<empreinte>   identité et état technique d'un élément
    pbi::slot|<clé>                       début d'une zone rédigée par l'utilisateur
    pbi::endslot                          fin de cette zone

Chaque marqueur occupe un paragraphe dont le texte porte l'attribut Word
« masqué » (`w:vanish`) : Word ne l'affiche ni ne l'imprime, et le paragraphe
ne prend aucune place tant que l'affichage du texte masqué est désactivé.
"""

import hashlib
from dataclasses import dataclass

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

PREFIX = "pbi::"

_ELEMENT = "elem"
_SLOT = "slot"
_SLOT_END = "endslot"

# Séparateur des champs d'un marqueur. Les identifiants d'éléments contiennent
# des « : » (`measure:Chiffre d'affaires`) mais jamais de barre verticale.
_SEPARATOR = "|"

_FINGERPRINT_LENGTH = 10


@dataclass(frozen=True)
class Marker:
    """Marqueur reconnu dans un document."""

    kind: str  # "elem", "slot" ou "endslot"
    value: str = ""  # identifiant d'élément, ou clé de zone
    fingerprint: str = ""


# ─────────────────────────────────────────────────────────────
#  Écriture
# ─────────────────────────────────────────────────────────────


def element(element_id: str, fingerprint: str) -> str:
    return f"{PREFIX}{_ELEMENT}{_SEPARATOR}{element_id}{_SEPARATOR}{fingerprint}"


def slot(key: str) -> str:
    return f"{PREFIX}{_SLOT}{_SEPARATOR}{key}"


def slot_end() -> str:
    return f"{PREFIX}{_SLOT_END}"


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
    run = paragraph.add_run(text)
    hide(run)


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

    body = text[len(PREFIX) :]
    kind, _, rest = body.partition(_SEPARATOR)

    if kind == _SLOT_END:
        return Marker(kind=_SLOT_END)
    if kind == _SLOT and rest:
        return Marker(kind=_SLOT, value=rest)
    if kind == _ELEMENT and _SEPARATOR in rest:
        value, _, digest = rest.rpartition(_SEPARATOR)
        return Marker(kind=_ELEMENT, value=value, fingerprint=digest)
    return None


def is_element(marker: Marker) -> bool:
    return marker.kind == _ELEMENT


def is_slot(marker: Marker) -> bool:
    return marker.kind == _SLOT


def is_slot_end(marker: Marker) -> bool:
    return marker.kind == _SLOT_END


def slot_key(element_id: str, block_id: str) -> str:
    """
    Clé d'une zone rédigée par l'utilisateur.

    Elle est préfixée par l'élément qui la contient : le bloc `mesure_notes`
    d'une mesure n'est pas celui d'une autre. Les zones situées hors de toute
    boucle n'ont pas de préfixe.
    """
    return f"{element_id}#{block_id}" if element_id else f"#{block_id}"
