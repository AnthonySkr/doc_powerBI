"""
Marqueurs invisibles posés dans le document généré.

Deux niveaux, et un principe : **le script est propriétaire de ses données,
l'utilisateur du reste.**

    pbi::elem|<identifiant>|<empreinte>   ancre un élément documenté
    pbi::gen|<bloc>  ...  pbi::endgen|<empreintes>
                                          encadrent un contenu produit par le
                                          script ; le marqueur de fin retient
                                          l'empreinte de chaque paragraphe et
                                          tableau écrits
    pbi::seed|<bloc> ...  pbi::endseed|<empreintes>
                                          encadrent une **amorce** : un contenu
                                          écrit à la première génération, puis
                                          laissé à l'utilisateur. Même forme que
                                          `gen`, politique inverse — c'est la
                                          version du document qui l'emporte

Les deux encadrements donnent une identité aux blocs du plan. Sans elle, un
bloc ajouté au plan ne pouvait pas être distingué du contenu libre de
l'utilisateur, et n'apparaissait jamais dans les éléments déjà documentés.

Tout ce qui se trouve entre deux ancres sans être encadré appartient à
l'utilisateur : titre reformulé, note ajoutée, capture collée, mise en forme.

À la régénération, un contenu `gen` est toujours réécrit — c'est une donnée du
rapport. Une amorce `seed` ne l'est que si personne n'y a touché : dès qu'on y
a écrit, c'est la version du document qui l'emporte. Les empreintes du marqueur
de fin disent, contenu par contenu, ce que le script avait écrit : elles
permettent de reconnaître cette différence, et de rendre à l'utilisateur ce
qu'on retrouve en plus à l'intérieur de l'encadrement (voir `merge.salvage`).

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
SEED = "seed"
SEED_END = "endseed"

# Encadrements : marqueur d'ouverture -> marqueur de fermeture.
ENCLOSURES = {GENERATED: GENERATED_END, SEED: SEED_END}
CLOSINGS = frozenset(ENCLOSURES.values())

# Les ancres que la fusion pose pour elle-même — et non pour le plan — portent
# ce préfixe : elles ne décrivent rien du rapport documenté.
INTERNAL_PREFIX = "merge:"

# Séparateur des champs. Les identifiants d'éléments contiennent des « : »
# (`measure:Chiffre d'affaires`) mais jamais de barre verticale.
_SEPARATOR = "|"

_FINGERPRINT_LENGTH = 10

_TEXT = qn("w:t")
_PARAGRAPH = qn("w:p")

# Contenus qui ne laissent aucun texte derrière eux : image, objet incorporé,
# forme dessinée. Un paragraphe qui n'en porte pas et n'a pas de texte est vide.
_PICTURES = (qn("w:drawing"), qn("w:pict"), qn("w:object"))
_PICTURE_MARK = "\u0001image"

_TABLE = qn("w:tbl")

# Contenus que Word calcule lui-même : table des matières, renvois, numéros. Le
# texte qu'on y lit est le sien, pas celui de l'utilisateur.
_FIELDS = (qn("w:fldChar"), qn("w:instrText"), qn("w:fldSimple"), qn("w:sdt"))


@dataclass(frozen=True)
class Marker:
    """Marqueur reconnu dans un document."""

    kind: str  # "elem", "gen", "endgen", "seed" ou "endseed"
    value: str = ""  # identifiant d'élément, ou identifiant de bloc du plan
    fingerprint: str = ""
    # Empreintes des contenus écrits par le script, portées par `endgen`.
    # None : marqueur d'un document produit par une version antérieure, qui
    # ne les portait pas encore.
    digests: tuple[str, ...] | None = None


# ─────────────────────────────────────────────────────────────
#  Écriture
# ─────────────────────────────────────────────────────────────


def element(element_id: str, fingerprint: str) -> str:
    return f"{PREFIX}{ELEMENT}{_SEPARATOR}{element_id}{_SEPARATOR}{fingerprint}"


def opening(kind: str, block_id: str) -> str:
    """Marqueur ouvrant un encadrement (`gen` ou `seed`)."""
    return f"{PREFIX}{kind}{_SEPARATOR}{block_id}"


def closing(kind: str, digests: list[str] | tuple[str, ...] = ()) -> str:
    """
    Marqueur fermant un encadrement, portant l'empreinte de chaque contenu écrit.

    Le séparateur est toujours écrit, même sans contenu : c'est lui qui
    distingue un bloc qui n'a rien produit d'un marqueur d'ancienne version.
    """
    return f"{PREFIX}{ENCLOSURES[kind]}{_SEPARATOR}{' '.join(digests)}"


def fingerprint(text: str) -> str:
    """
    Empreinte du contenu technique d'un élément (expression DAX, champs d'un
    visuel...). Une empreinte plutôt que le texte lui-même : le marqueur reste
    court et ne recopie pas le contenu du document dans du texte masqué.
    """
    normalized = " ".join((text or "").split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]


# Empreinte d'un contenu sans texte ni image : la place laissée libre par le
# script en fin de bloc. Ce qu'on y écrit ne remplace rien.
EMPTY = fingerprint("")


def digest(node) -> str:
    """
    Empreinte du contenu d'un élément de corps (paragraphe ou tableau).

    Elle est prise au moment de l'écriture, puis retrouvée telle quelle à la
    relecture tant que personne n'a touché à l'élément. Une image est notée :
    une capture collée dans un paragraphe laissé vide doit se voir.
    """
    content = text(node)
    return fingerprint(f"{_PICTURE_MARK} {content}" if has_picture(node) else content)


def text(node) -> str:
    """Texte porté par un élément XML, tous ses descendants réunis."""
    return "".join(run.text or "" for run in node.iter(_TEXT))


def has_content(node) -> bool:
    """L'élément porte-t-il quelque chose : du texte, une image, un tableau ?"""
    return node.tag == _TABLE or bool(text(node).strip()) or has_picture(node)


def is_field(node) -> bool:
    """
    L'élément est-il un contenu que Word calcule — table des matières, renvoi ?

    Son texte change tout seul d'une ouverture à l'autre : le comparer à ce que
    le script avait écrit n'a pas de sens, et le prendre pour de la rédaction
    en ferait un doublon à chaque génération.
    """
    return node.tag in _FIELDS or any(next(node.iter(tag), None) is not None for tag in _FIELDS)


def has_picture(node) -> bool:
    """L'élément porte-t-il une image, un objet incorporé ou une forme ?"""
    return any(next(node.iter(tag), None) is not None for tag in _PICTURES)


def write(doc, text: str):
    """Ajoute au document un paragraphe masqué portant le marqueur, et le retourne."""
    paragraph = doc.add_paragraph()
    hide(paragraph.add_run(text))
    return paragraph


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

    kind, separator, rest = text[len(PREFIX) :].partition(_SEPARATOR)

    if kind in CLOSINGS:
        return Marker(kind=kind, digests=tuple(rest.split()) if separator else None)
    if kind in ENCLOSURES and rest:
        return Marker(kind=kind, value=rest)
    if kind == ELEMENT and _SEPARATOR in rest:
        value, _, digest = rest.rpartition(_SEPARATOR)
        return Marker(kind=ELEMENT, value=value, fingerprint=digest)
    return None


def of(node) -> Marker | None:
    """Marqueur porté par un élément XML de corps de document (`w:p`), sinon None."""
    return parse(text(node)) if node.tag == _PARAGRAPH else None
