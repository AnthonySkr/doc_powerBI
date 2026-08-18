"""
Lecture d'un document généré : repérage des items et des blocs suivis.

Le générateur pose un signet sur le titre de chaque item documenté (page,
visuel, table, mesure) et autour de chaque bloc « suivi ». Ce module relit ces
signets pour retrouver, dans un document déjà écrit, l'emplacement exact de
chaque item et de chaque bloc : c'est ce qui permet de comparer deux versions
et de ne remplacer que ce qui a changé.
"""

from dataclasses import dataclass, field
from typing import Any

from docx.oxml.ns import qn

# Éléments de corps de document pris en compte dans les plages.
_BLOCK_TAGS = (qn("w:p"), qn("w:tbl"))


@dataclass
class BlockRange:
    """Suite d'éléments encadrée par le signet d'un bloc suivi."""

    bookmark: str
    elements: list[Any] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(_element_text(element) for element in self.elements).strip()

    def styles(self) -> set[str]:
        """Identifiants des styles de paragraphe utilisés par le bloc."""
        found = set()
        for element in self.elements:
            for style in element.iter(qn("w:pStyle")):
                found.add(style.get(qn("w:val")))
        return found


@dataclass
class DocItem:
    """Section documentée : son titre, son contenu et ses blocs suivis."""

    bookmark: str
    title: str
    level: int
    heading: Any
    elements: list[Any] = field(default_factory=list)
    blocks: dict[str, BlockRange] = field(default_factory=dict)

    @property
    def last_element(self) -> Any:
        return self.elements[-1] if self.elements else self.heading


@dataclass
class DocIndex:
    """Vue d'un document : ses items, dans l'ordre du document."""

    items: dict[str, DocItem] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    body: Any = None

    def get(self, bookmark: str) -> DocItem | None:
        return self.items.get(bookmark)


def index_document(
    doc,
    heading_styles: dict[str, int],
    block_names: dict[str, str],
    ignored_run_styles: set[str] | None = None,
) -> DocIndex:
    """
    Indexe un document.

    Args:
        doc: document python-docx
        heading_styles: identifiant de style de titre -> niveau (Titre2 -> 2)
        block_names: nom de signet d'un bloc suivi -> identifiant du bloc
        ignored_run_styles: styles de caractère à ignorer dans les titres
            (mention technique ajoutée à la suite du nom d'un visuel)

    Returns:
        Un DocIndex donnant, pour chaque signet d'item, sa plage d'éléments.
    """
    body = doc.element.body
    children = [child for child in body if child.tag in _BLOCK_TAGS]

    index = DocIndex(body=body)
    open_items: list[DocItem] = []

    for position, element in enumerate(children):
        level = _heading_level(element, heading_styles)
        bookmark = _first_bookmark(element)

        if level is not None:
            # Un titre ferme les items de niveau supérieur ou égal.
            while open_items and open_items[-1].level >= level:
                open_items.pop()

            if bookmark:
                item = DocItem(
                    bookmark=bookmark,
                    title=_element_text(element, ignored_run_styles),
                    level=level,
                    heading=element,
                    elements=[element],
                )
                index.items[bookmark] = item
                index.order.append(bookmark)
                open_items.append(item)
                for parent in open_items[:-1]:
                    parent.elements.append(element)
                continue

        for item in open_items:
            item.elements.append(element)

    _index_blocks(children, index, block_names)
    return index


def _index_blocks(children: list[Any], index: DocIndex, block_names: dict[str, str]) -> None:
    """Associe à chaque item les plages de ses blocs suivis."""
    ranges = _bookmark_ranges(index.body, children, set(block_names))

    for bookmark, elements in ranges.items():
        if not elements:
            continue
        block_id = block_names[bookmark]

        # Un item de niveau 2 contient les items de niveau 3 : le bloc revient
        # au plus profond de ceux qui l'englobent.
        owner = None
        for item in index.items.values():
            if any(elements[0] is element for element in item.elements) and (
                owner is None or item.level > owner.level
            ):
                owner = item
        if owner is not None:
            owner.blocks[block_id] = BlockRange(bookmark=bookmark, elements=elements)


def _bookmark_ranges(body: Any, children: list[Any], wanted: set[str]) -> dict[str, list[Any]]:
    """
    Plage d'éléments couverte par chaque signet recherché.

    Le générateur place `w:bookmarkStart` avant le premier élément du bloc et
    `w:bookmarkEnd` après le dernier : un seul parcours du corps du document
    suffit à retrouver les deux bornes.
    """
    position = {id(element): index for index, element in enumerate(children)}
    starts: dict[str, tuple[str, int]] = {}  # id du signet -> (nom, position)
    ranges: dict[str, list[Any]] = {}
    seen = 0

    for element in body:
        if element.tag == qn("w:bookmarkStart"):
            name = element.get(qn("w:name"))
            if name in wanted:
                starts[element.get(qn("w:id"))] = (name, seen)
        elif element.tag == qn("w:bookmarkEnd"):
            opened = starts.pop(element.get(qn("w:id")), None)
            if opened is not None:
                name, first = opened
                ranges[name] = children[first:seen]
        elif id(element) in position:
            seen = position[id(element)] + 1

    # Signets restés ouverts (fin absente) : plage jusqu'au dernier élément vu.
    for name, first in starts.values():
        ranges.setdefault(name, children[first:seen])

    return ranges


def _heading_level(element: Any, heading_styles: dict[str, int]) -> int | None:
    """Niveau de titre d'un paragraphe, ou None si ce n'en est pas un."""
    if element.tag != qn("w:p"):
        return None
    style = element.find(qn("w:pPr") + "/" + qn("w:pStyle"))
    if style is None:
        return None
    return heading_styles.get(style.get(qn("w:val")))


def _first_bookmark(element: Any) -> str | None:
    """Nom du premier signet posé dans un paragraphe (signet d'item)."""
    for start in element.iter(qn("w:bookmarkStart")):
        name = start.get(qn("w:name"))
        if name and not name.startswith("_"):  # « _Toc… » : signets de sommaire
            return name
    return None


def _element_text(element: Any, ignored_run_styles: set[str] | None = None) -> str:
    """
    Texte d'un paragraphe ou d'un tableau.

    Les passages écrits dans un style de caractère ignoré (mention technique
    à la suite d'un titre) sont laissés de côté.
    """
    ignored = ignored_run_styles or set()
    parts = []
    for run in element.iter(qn("w:r")):
        style = run.find(qn("w:rPr") + "/" + qn("w:rStyle"))
        if style is not None and style.get(qn("w:val")) in ignored:
            continue
        parts.append("".join(node.text or "" for node in run.iter(qn("w:t"))))
    return "".join(parts).strip()
