"""
Découpage du corps d'un document en blocs ancrés.

Un bloc va d'une ancre `pbi::elem` à la suivante. À l'intérieur, on distingue
trois natures de contenu :

    owned  encadré par `pbi::gen|<bloc>` … `pbi::endgen` — produit par le
           script, réécrit à chaque génération
    seed   encadré par `pbi::seed|<bloc>` … `pbi::endseed` — une amorce, écrite
           à la première génération puis laissée à l'utilisateur
    free   tout le reste — écrit ou remanié par l'utilisateur, sans identité
           propre : il est repéré par le segment identifié qui le précède

Les segments `owned` et `seed` retiennent au passage les empreintes portées par
leur marqueur de fin : elles disent ce que le script avait écrit, et donc, par
différence, ce que l'utilisateur a glissé à l'intérieur (voir `merge.salvage`).

Le même découpage sert pour le document précédent et pour celui qui vient
d'être généré : la fusion consiste à superposer les deux (voir `merge.smart`).
"""

from dataclasses import dataclass, field

from docx.oxml.ns import qn

from src.merge import markers

OWNED = "owned"
SEED = "seed"
FREE = "free"

# Natures de segment portant un identifiant de bloc du plan.
IDENTIFIED = (OWNED, SEED)

# Nature de segment correspondant à chaque marqueur d'ouverture.
_KINDS = {markers.GENERATED: OWNED, markers.SEED: SEED}

_SECTION_PROPERTIES = qn("w:sectPr")


@dataclass
class Segment:
    """Suite d'éléments XML consécutifs de même nature."""

    kind: str  # OWNED, SEED ou FREE
    block_id: str = ""  # identifiant du bloc du plan, pour un segment identifié
    nodes: list = field(default_factory=list)
    # Empreintes des contenus que le script avait écrits, relevées sur le
    # marqueur de fin d'un segment identifié. None : le marqueur n'en portait
    # pas (document produit par une version antérieure).
    digests: tuple[str, ...] | None = None

    @property
    def identified(self) -> bool:
        return self.kind in IDENTIFIED

    def content_nodes(self) -> list:
        """Les éléments du segment, sans les marqueurs qui l'encadrent."""
        return [node for node in self.nodes if markers.of(node) is None]


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

    @property
    def block_ids(self) -> list[str]:
        """Identifiants des segments identifiés, dans l'ordre du document."""
        return [s.block_id for s in self.segments if s.identified]

    def free_nodes(self) -> list:
        return [node for segment in self.segments if segment.kind == FREE for node in segment.nodes]

    def identified_segments(self) -> dict[str, Segment]:
        """Segments identifiés, par identifiant de bloc (le premier l'emporte)."""
        found: dict[str, Segment] = {}
        for segment in self.segments:
            if segment.identified and segment.block_id not in found:
                found[segment.block_id] = segment
        return found

    def free_after(self) -> dict[str, list]:
        """
        Contenu libre de l'utilisateur, rangé sous le segment identifié qui le
        précède — `""` pour ce qui ouvre le bloc (le titre, notamment).

        C'est ce repérage relatif qui permet de replacer la rédaction quand le
        plan a changé : elle suit le bloc auquel elle se rapporte, pas un rang
        absolu qui aurait glissé.
        """
        placed: dict[str, list] = {}
        key = ""
        for segment in self.segments:
            if segment.identified:
                key = segment.block_id
            else:
                placed.setdefault(key, []).extend(segment.nodes)
        return placed


def body_nodes(document) -> list:
    """Éléments de premier niveau du corps (`w:p`, `w:tbl`), hors `w:sectPr`."""
    return [node for node in document.element.body if node.tag != _SECTION_PROPERTIES]


def parse(nodes: list) -> list[Block]:
    """Découpe une suite d'éléments de corps en blocs ancrés."""
    blocks = [Block()]
    open_kind: str | None = None

    for node in nodes:
        marker = markers.of(node)

        if marker is None:
            _append(blocks[-1], open_kind or FREE, _open_id(blocks[-1], open_kind), node)
            continue

        if marker.kind == markers.ELEMENT:
            blocks.append(
                Block(element_id=marker.value, fingerprint=marker.fingerprint, anchor=node)
            )
            open_kind = None
        elif marker.kind in _KINDS:
            open_kind = _KINDS[marker.kind]
            # Le segment porte ses propres délimiteurs : réémis avec lui, ils
            # gardent le contenu reconnaissable à la génération suivante. Un
            # segment vide reste utile : il retient la place du bloc dans
            # l'ordre voulu par l'utilisateur.
            blocks[-1].segments.append(Segment(kind=open_kind, block_id=marker.value, nodes=[node]))
        elif marker.kind in (markers.GENERATED_END, markers.SEED_END):
            if open_kind is not None:
                blocks[-1].segments[-1].nodes.append(node)
                blocks[-1].segments[-1].digests = marker.digests
            open_kind = None

    return blocks


def index(blocks: list[Block]) -> dict[str, Block]:
    """Blocs indexés par identifiant d'élément (le contenu hors ancre est écarté)."""
    return {block.element_id: block for block in blocks if block.element_id}


def _open_id(block: Block, open_kind: str | None) -> str:
    return block.segments[-1].block_id if open_kind is not None and block.segments else ""


def _append(block: Block, kind: str, block_id: str, node) -> None:
    if (
        block.segments
        and block.segments[-1].kind == kind
        and block.segments[-1].block_id == block_id
    ):
        block.segments[-1].nodes.append(node)
    else:
        block.segments.append(Segment(kind=kind, block_id=block_id, nodes=[node]))
