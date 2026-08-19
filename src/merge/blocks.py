"""
Découpage du corps d'un document en blocs ancrés.

Un bloc va d'une ancre `pbi::elem` à la suivante. À l'intérieur, on distingue
seulement deux natures de contenu :

    owned  encadré par `pbi::gen|<bloc>` … `pbi::endgen` — produit par le script
    free   tout le reste — écrit ou remanié par l'utilisateur

Le même découpage sert pour le document précédent et pour celui qui vient
d'être généré : la fusion consiste à superposer les deux.
"""

from dataclasses import dataclass, field

from docx.oxml.ns import qn

from src.merge import markers

OWNED = "owned"
FREE = "free"

_SECTION_PROPERTIES = qn("w:sectPr")


@dataclass
class Segment:
    """Suite d'éléments XML consécutifs de même nature."""

    kind: str  # OWNED ou FREE
    block_id: str = ""  # identifiant du bloc du plan, pour un segment OWNED
    nodes: list = field(default_factory=list)


@dataclass
class Block:
    """Contenu d'un élément documenté, de son ancre à la suivante."""

    element_id: str = ""  # vide pour le contenu précédant la première ancre
    fingerprint: str = ""
    anchor: object | None = None  # le paragraphe portant l'ancre
    segments: list[Segment] = field(default_factory=list)

    @property
    def owned_ids(self) -> list[str]:
        return [s.block_id for s in self.segments if s.kind == OWNED]

    def free_nodes(self) -> list:
        return [node for segment in self.segments if segment.kind == FREE for node in segment.nodes]


def body_nodes(document) -> list:
    """Éléments de premier niveau du corps (`w:p`, `w:tbl`), hors `w:sectPr`."""
    return [node for node in document.element.body if node.tag != _SECTION_PROPERTIES]


def parse(nodes: list) -> list[Block]:
    """Découpe une suite d'éléments de corps en blocs ancrés."""
    blocks = [Block()]
    owned_id: str | None = None

    for node in nodes:
        marker = markers.of(node)

        if marker is None:
            _append(blocks[-1], OWNED if owned_id is not None else FREE, owned_id or "", node)
            continue

        if marker.kind == markers.ELEMENT:
            blocks.append(
                Block(element_id=marker.value, fingerprint=marker.fingerprint, anchor=node)
            )
            owned_id = None
        elif marker.kind == markers.GENERATED:
            owned_id = marker.value
            # Le segment porte ses propres délimiteurs : réémis avec lui, ils
            # gardent le contenu reconnaissable à la génération suivante. Un
            # segment vide reste utile : il retient la place du bloc dans
            # l'ordre voulu par l'utilisateur.
            blocks[-1].segments.append(Segment(kind=OWNED, block_id=owned_id, nodes=[node]))
        elif marker.kind == markers.GENERATED_END:
            if owned_id is not None:
                blocks[-1].segments[-1].nodes.append(node)
            owned_id = None

    return blocks


def index(blocks: list[Block]) -> dict[str, Block]:
    """Blocs indexés par identifiant d'élément (le contenu hors ancre est écarté)."""
    return {block.element_id: block for block in blocks if block.element_id}


def _append(block: Block, kind: str, block_id: str, node) -> None:
    if (
        block.segments
        and block.segments[-1].kind == kind
        and block.segments[-1].block_id == block_id
    ):
        block.segments[-1].nodes.append(node)
    else:
        block.segments.append(Segment(kind=kind, block_id=block_id, nodes=[node]))
