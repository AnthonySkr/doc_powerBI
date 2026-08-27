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

Les marqueurs occupent un paragraphe à eux, masqué de bout en bout : son texte
porte l'attribut Word « masqué » (`w:vanish`), et sa marque de paragraphe
aussi. C'est la seconde qui décide de la mise en page — masquer le seul texte
laisse la ligne vide et l'écart d'après-paragraphe du style, quelques
millimètres par marqueur et une bonne respiration de trop entre deux blocs.
Marque masquée, Word joint le paragraphe au suivant : le marqueur ne prend
plus aucune place. Et quand l'utilisateur affiche le texte masqué pour voir
ce que le script a posé, le paragraphe est déjà réduit au minimum — 1 pt,
sans écart ni interligne (voir `collapse`).
"""

import hashlib
from dataclasses import dataclass

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

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
_RUN_PROPERTIES = qn("w:rPr")
_SECTION = qn("w:sectPr")

# Taille du texte d'un marqueur, et hauteur de sa ligne : le minimum que Word
# accepte. Elle ne se voit que si l'utilisateur affiche le texte masqué.
_MARKER_SIZE = Pt(1)

# Contenus qui ne laissent aucun texte derrière eux : image, objet incorporé,
# forme dessinée. Un paragraphe qui n'en porte pas et n'a pas de texte est vide.
_PICTURES = (qn("w:drawing"), qn("w:pict"), qn("w:object"))
_PICTURE_MARK = "\u0001image"

# Formes flottantes — les repères numérotés posés sous une capture. Elles ne
# portent que leur numéro : seule leur position dit qu'on y a touché.
_ANCHOR = qn("wp:anchor")
_POSITIONS = (qn("wp:posOffset"), qn("wp:align"))
_ANCHOR_MARK = "\u0001repere"

_TABLE = qn("w:tbl")

# Contenus que Word calcule lui-même : table des matières, renvois, numéros. Le
# texte qu'on y lit est le sien, pas celui de l'utilisateur.
_FIELDS = (qn("w:fldChar"), qn("w:instrText"), qn("w:fldSimple"), qn("w:sdt"))

_FIELD_CHAR = qn("w:fldChar")
_FIELD_CHAR_TYPE = qn("w:fldCharType")
_SIMPLE_FIELD = qn("w:fldSimple")


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
    relecture tant que personne n'a touché à l'élément. Trois choses la
    composent, chacune parce qu'un geste de l'utilisateur doit se voir :

      - le texte écrit, sans les résultats de champs — un numéro de figure que
        Word recalcule ne dit rien de ce que l'utilisateur a fait ;
      - la présence d'une image : une capture collée dans un paragraphe laissé
        vide doit se voir ;
      - la position des formes flottantes : un repère glissé sur la capture ne
        change rien d'autre, et c'est pourtant tout le travail.
    """
    marks = []
    if has_picture(node):
        marks.append(_PICTURE_MARK)
    positions = _positions(node)
    if positions:
        marks.append(f"{_ANCHOR_MARK} {positions}")

    content = written_text(node)
    return fingerprint(" ".join([*marks, content]) if marks else content)


def text(node) -> str:
    """Texte porté par un élément XML, tous ses descendants réunis."""
    return "".join(run.text or "" for run in node.iter(_TEXT))


def written_text(node) -> str:
    """
    Le texte de l'élément, sans ce que Word calcule lui-même.

    Le résultat d'un champ — numéro de figure, renvoi, numéro de page — change
    d'une ouverture à l'autre sans que personne n'y touche. Le retenir ferait
    passer pour rédigée une légende que Word vient simplement de renuméroter.
    """
    parts: list[str] = []
    depth = 0
    for element in node.iter(_TEXT, _FIELD_CHAR):
        if element.tag == _FIELD_CHAR:
            kind = element.get(_FIELD_CHAR_TYPE)
            if kind == "begin":
                depth += 1
            elif kind == "end":
                depth = max(depth - 1, 0)
        elif depth == 0 and not _inside_simple_field(element, node):
            parts.append(element.text or "")
    return "".join(parts)


def _inside_simple_field(element, root) -> bool:
    """Le nœud est-il dans un champ de forme condensée (`w:fldSimple`) ?"""
    parent = element.getparent()
    while parent is not None and parent is not root:
        if parent.tag == _SIMPLE_FIELD:
            return True
        parent = parent.getparent()
    return False


def _positions(node) -> str:
    """Positions des formes flottantes que porte l'élément, dans leur ordre."""
    return " ".join(
        position.text or ""
        for anchor in node.iter(_ANCHOR)
        for position in anchor.iter(*_POSITIONS)
    )


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
    collapse(paragraph._p)
    return paragraph


def hide(run) -> None:
    """Applique l'attribut « masqué » à un run, et le réduit à 1 pt."""
    _vanish(run._r.get_or_add_rPr())


def collapse(node) -> None:
    """
    Retire au paragraphe d'un marqueur la place qu'il prendrait.

    Masquer le texte ne suffit pas : la marque de paragraphe, elle, reste
    affichée, et avec elle une ligne et l'écart d'après-paragraphe du style —
    quelques millimètres par marqueur, et jusqu'à quatre marqueurs entre deux
    contenus rédigés. Masquer aussi la marque de paragraphe fait disparaître la
    ligne entière : Word joint le paragraphe au suivant tant que l'affichage du
    texte masqué est désactivé.

    Le reste — écarts nuls, interligne fixé à 1 pt — vaut pour le moment où
    l'utilisateur affiche le texte masqué : les marqueurs se voient alors, mais
    sans écarter le document qu'ils encadrent.

    Rien n'est demandé au template : un marqueur ne doit pas dépendre d'un
    style que le document de l'utilisateur pourrait ne pas avoir.
    """
    properties = node.get_or_add_pPr()

    spacing = properties.get_or_add_spacing()
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), str(_MARKER_SIZE.twips))
    spacing.set(qn("w:lineRule"), "exact")

    _vanish(_mark_properties(properties))


def collapse_all(doc) -> None:
    """
    Réduit tous les marqueurs du document terminé.

    La fusion recopie les marqueurs du document précédent avec ce qu'ils
    encadrent : sans ce passage, une documentation produite par une version
    antérieure garderait ses marqueurs encombrants là où elle n'a pas été
    réécrite. Un document régénéré est donc entièrement resserré, même sur ce
    qui vient de l'ancien.
    """
    for node in doc.element.body.iter(_PARAGRAPH):
        if of(node) is not None:
            collapse(node)


def _mark_properties(properties):
    """Propriétés de la marque de paragraphe (`w:pPr/w:rPr`), créées au besoin."""
    mark = properties.find(_RUN_PROPERTIES)
    if mark is None:
        mark = OxmlElement("w:rPr")
        # `w:rPr` se place après les propriétés de mise en forme, et avant la
        # rupture de section quand le paragraphe en porte une.
        section = properties.find(_SECTION)
        index = list(properties).index(section) if section is not None else len(properties)
        properties.insert(index, mark)
    return mark


def _vanish(properties) -> None:
    """Masque un texte et le réduit à 1 pt, marque de paragraphe comprise."""
    properties.get_or_add_vanish()
    properties.get_or_add_sz().val = _MARKER_SIZE


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
