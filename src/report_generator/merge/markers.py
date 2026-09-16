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

Les encadrements donnent une identité aux blocs du plan : sans elle, un bloc
ajouté ne se distinguerait pas du contenu libre de l'utilisateur, et
n'arriverait jamais dans un document déjà généré. Tout ce qui se trouve entre
deux ancres sans être encadré lui appartient.

À la régénération, un contenu `gen` est toujours réécrit — c'est une donnée du
rapport. Une amorce `seed` ne l'est que si personne n'y a touché. Les
empreintes du marqueur de fin disent, contenu par contenu, ce que le script
avait écrit : c'est ainsi qu'on rend à l'utilisateur ce qu'on retrouve en plus
à l'intérieur d'un encadrement (voir `merge.salvage`).

Un marqueur occupe un paragraphe à lui, masqué de bout en bout — texte *et*
marque de paragraphe (`w:vanish`). C'est la seconde qui compte pour la mise en
page : sans elle, Word garde la ligne vide et l'écart du style, soit une bonne
respiration de trop entre deux blocs. Marque masquée, le marqueur ne prend plus
aucune place ; ses écarts nuls et sa petite taille ne servent qu'à le laisser
lisible quand l'utilisateur affiche le texte masqué (voir `collapse`).

Un marqueur se lit sur le seul texte du paragraphe : celui d'une forme
flottante qu'on y a ancrée — un repère déposé sur une image — ne lui appartient
pas (voir `own_text`).
"""

import hashlib
from dataclasses import dataclass

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

PREFIX = "pbi::"
"""En tête de tout marqueur : c'est à lui qu'on en reconnaît un."""

ELEMENT = "elem"
"""Ancre un élément documenté, et porte son empreinte."""

GENERATED = "gen"
"""Ouvre un contenu du script, réécrit à chaque génération."""

GENERATED_END = "endgen"
"""Le ferme, et porte l'empreinte de chaque contenu écrit."""

SEED = "seed"
"""Ouvre une amorce : écrite une fois, puis laissée à l'utilisateur."""

SEED_END = "endseed"
"""La ferme, et porte l'empreinte de ce qu'elle contenait."""

ENCLOSURES = {GENERATED: GENERATED_END, SEED: SEED_END}
"""Encadrements : marqueur d'ouverture → marqueur de fermeture."""

CLOSINGS = frozenset(ENCLOSURES.values())
"""Les marqueurs qui ferment un encadrement."""

INTERNAL_PREFIX = "merge:"
"""
Préfixe des ancres que la fusion pose pour elle-même.

Elles ne décrivent rien du rapport documenté, et ne comptent donc pas parmi
les éléments qu'il aurait perdus.
"""

# Séparateur des champs. Les identifiants d'éléments contiennent des « : »
# (`measure:Chiffre d'affaires`) mais jamais de barre verticale.
_SEPARATOR = "|"

_FINGERPRINT_LENGTH = 10

_TEXT = qn("w:t")
_PARAGRAPH = qn("w:p")
_RUN_PROPERTIES = qn("w:rPr")
_SECTION = qn("w:sectPr")

# Taille du texte d'un marqueur. Elle ne se voit qu'en affichage du texte
# masqué : le reste du temps le paragraphe n'existe pas pour la mise en page,
# on peut donc la garder lisible plutôt que minuscule.
_MARKER_SIZE = Pt(5)

# Hauteur de sa ligne, fixée un peu au-dessus du texte : à l'exacte taille de
# la police, Word rogne le haut des caractères.
_MARKER_LINE = Pt(6)

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
_INSTRUCTION_TEXT = qn("w:instrText")
_INSTRUCTION = qn("w:instr")

# Champs dont le résultat ne bouge pas : Word ne le recalcule jamais. Un lien
# en fait partie — son libellé est le texte que le script a posé. Word réécrit
# volontiers un lien interne sous cette forme ; l'écarter de l'empreinte ferait
# passer pour rédigé un contenu auquel personne n'a touché.
_STABLE_FIELDS = ("HYPERLINK",)


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
    """Marqueur ancrant un élément documenté, avec son empreinte."""
    return f"{PREFIX}{ELEMENT}{_SEPARATOR}{element_id}{_SEPARATOR}{fingerprint}"


def opening(kind: str, block_id: str) -> str:
    """Marqueur ouvrant un encadrement (`gen` ou `seed`)."""
    return f"{PREFIX}{kind}{_SEPARATOR}{block_id}"


def closing(kind: str, digests: list[str] | tuple[str, ...] = ()) -> str:
    """
    Marqueur fermant un encadrement, avec l'empreinte de chaque contenu écrit.

    Le séparateur est écrit même sans contenu : c'est lui qui distingue un bloc
    qui n'a rien produit d'un marqueur d'ancienne version.
    """
    return f"{PREFIX}{ENCLOSURES[kind]}{_SEPARATOR}{' '.join(digests)}"


def fingerprint(text: str) -> str:
    """
    Empreinte du contenu technique d'un élément — expression DAX, champs.

    Une empreinte plutôt que le texte : le marqueur reste court, et ne recopie
    pas le document dans du texte masqué.
    """
    normalized = " ".join((text or "").split())
    # `usedforsecurity=False` : ce condensé identifie un contenu, il ne
    # protège rien. Sans lui, un poste Windows en mode FIPS refuse md5 et
    # toute la fusion tombe.
    digest = hashlib.md5(normalized.encode("utf-8"), usedforsecurity=False)
    return digest.hexdigest()[:_FINGERPRINT_LENGTH]


EMPTY = fingerprint("")
"""
Empreinte d'un contenu sans texte ni image.

C'est la place que le script laisse libre en fin de bloc : ce qu'on y écrit ne
remplace rien, et appartient donc à l'utilisateur.
"""


def digest(node) -> str:
    """
    Empreinte du contenu d'un paragraphe ou d'un tableau.

    Prise à l'écriture, elle se retrouve identique tant que personne n'a
    touché à l'élément. Trois choses la composent, chacune parce qu'un geste
    de l'utilisateur doit se voir :

      - le texte écrit, sans les résultats de champs — un numéro que Word
        recalcule ne dit rien de ce que l'utilisateur a fait ;
      - la présence d'une image, collée dans un paragraphe laissé vide ;
      - la position des formes flottantes : un repère glissé sur l'image ne
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


def own_text(node) -> str:
    """
    Le texte du paragraphe seul, sans celui des formes qui y flottent.

    Une forme est *ancrée* dans un paragraphe sans lui appartenir, et Word
    change son ancre pour le paragraphe le plus proche de l'endroit où on la
    dépose. Un repère glissé sur une image atterrit donc volontiers dans le
    paragraphe masqué qui la précède — celui du marqueur. Son numéro se
    collait alors au texte du marqueur, qui n'était plus reconnu : le bloc
    perdait son identité, et la régénération reposait un emplacement d'image
    par-dessus la capture déjà collée.
    """
    return "".join(run.text or "" for run in node.iter(_TEXT) if not _floats_over(run, node))


def _floats_over(element, node) -> bool:
    """Le texte est-il celui d'une forme ancrée dans l'élément, non le sien ?"""
    parent = element.getparent()
    while parent is not None and parent is not node:
        if parent.tag in _PICTURES:
            return True
        parent = parent.getparent()
    return False


def written_text(node) -> str:
    """
    Le texte de l'élément, sans ce que Word recalcule lui-même.

    Le résultat d'un champ — numéro de figure, renvoi, numéro de page — change
    d'une ouverture à l'autre sans que personne n'y touche : le retenir ferait
    passer pour rédigée une légende que Word vient de renuméroter.

    Un lien fait exception : Word réécrit volontiers un lien interne en champ
    `HYPERLINK`, mais son résultat est le libellé posé par le script, et il ne
    bouge plus.
    """
    parts: list[str] = []
    # Champs ouverts, du plus englobant au plus imbriqué : chacun retient son
    # instruction, puis si son résultat compte comme du texte écrit.
    fields: list[list] = []

    for element in node.iter(_TEXT, _FIELD_CHAR, _INSTRUCTION_TEXT):
        if element.tag == _FIELD_CHAR:
            kind = element.get(_FIELD_CHAR_TYPE)
            if kind == "begin":
                fields.append(["", False])
            elif kind == "separate" and fields:
                # L'instruction est complète : elle dit si ce qui suit est un
                # texte écrit une fois pour toutes ou un calcul de Word.
                fields[-1][1] = _is_stable(fields[-1][0])
            elif kind == "end" and fields:
                fields.pop()
        elif element.tag == _INSTRUCTION_TEXT:
            if fields:
                fields[-1][0] += element.text or ""
        elif all(stable for _, stable in fields) and not _recomputed_field(element, node):
            parts.append(element.text or "")

    return "".join(parts)


def same_content(left, right) -> bool:
    """
    Deux éléments portent-ils le même contenu, aux retouches de Word près ?

    L'empreinte relevée à l'écriture ne survit pas à tout : Word recoupe les
    runs, perd une espace, réécrit un lien en champ. Rien de cela n'est un
    geste de l'utilisateur, et la fusion doit reconnaître la donnée qu'elle
    s'apprête à réécrire à l'identique.

    La comparaison est donc tolérante : les espaces ne comptent pas, et les
    deux lectures du texte sont acceptées, avec et sans résultats de champs.
    Ce qui relève du geste de l'utilisateur, lui, se voit : une image collée
    dans une donnée du script, ou un repère qu'on a fait glisser.
    """
    if has_picture(left) != has_picture(right) or _positions(left) != _positions(right):
        return False
    return _squeezed(written_text(left)) == _squeezed(written_text(right)) or _squeezed(
        text(left)
    ) == _squeezed(text(right))


def _squeezed(value: str) -> str:
    """Le texte débarrassé de toutes ses espaces."""
    return "".join((value or "").split())


def _is_stable(instruction: str) -> bool:
    """Le résultat de ce champ est-il un texte écrit, que Word ne recalcule pas ?"""
    return (instruction or "").strip().upper().startswith(_STABLE_FIELDS)


def _recomputed_field(element, root) -> bool:
    """Le nœud est-il dans un champ de forme condensée (`w:fldSimple`) recalculé ?"""
    parent = element.getparent()
    while parent is not None and parent is not root:
        if parent.tag == _SIMPLE_FIELD and not _is_stable(parent.get(_INSTRUCTION)):
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
    L'élément est-il un contenu que Word calcule — sommaire, renvoi ?

    Son texte change tout seul d'une ouverture à l'autre : le prendre pour de
    la rédaction en ferait un doublon à chaque génération.
    """
    return node.tag in _FIELDS or any(next(node.iter(tag), None) is not None for tag in _FIELDS)


def has_picture(node) -> bool:
    """L'élément porte-t-il une image, un objet incorporé ou une forme ?"""
    return any(next(node.iter(tag), None) is not None for tag in _PICTURES)


def write(body, text: str):
    """
    Ajoute un paragraphe masqué portant le marqueur, et le retourne.

    `body` est ce qui sait ajouter un paragraphe : le `word.body.Body` du
    document en cours d'écriture, ou le document lui-même.
    """
    paragraph = body.add_paragraph()
    hide(paragraph.add_run(text))
    collapse(paragraph._p)
    return paragraph


def hide(run) -> None:
    """Masque un run, et le réduit à la taille d'un marqueur."""
    _vanish(run._r.get_or_add_rPr())


def collapse(node) -> None:
    """
    Retire au paragraphe d'un marqueur la place qu'il prendrait.

    Masquer le texte ne suffit pas : la marque de paragraphe reste affichée, et
    avec elle une ligne et l'écart du style — jusqu'à quatre marqueurs entre
    deux contenus rédigés. La masquer aussi fait disparaître la ligne entière.

    Le reste — écarts nuls, interligne fixe — vaut pour le moment où
    l'utilisateur affiche le texte masqué : les marqueurs s'y lisent sans
    écarter le document. Rien n'est demandé au template.
    """
    properties = node.get_or_add_pPr()

    spacing = properties.get_or_add_spacing()
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), str(_MARKER_LINE.twips))
    spacing.set(qn("w:lineRule"), "exact")

    _vanish(_mark_properties(properties))


def collapse_all(doc) -> None:
    """
    Réduit tous les marqueurs du document terminé.

    La fusion recopie ceux du document précédent avec ce qu'ils encadrent :
    sans ce passage, une documentation produite par une version antérieure
    garderait ses marqueurs encombrants là où elle n'a pas été réécrite.
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
    """Pose « masqué » et la taille d'un marqueur sur des propriétés de run."""
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
    return parse(own_text(node)) if node.tag == _PARAGRAPH else None
