"""
Fusion du document fraîchement généré avec le précédent.

Le contrat : le script est propriétaire des contenus qu'il a produits, marqués
`pbi::gen`. Tout le reste appartient à l'utilisateur.

Pour chaque élément documenté, on suit l'ordre du **document précédent** — donc
celui voulu par l'utilisateur — et on n'y remplace que les contenus du script :

    ancien bloc                            bloc reconstruit
    ─────────────────────────────────────  ────────────────────────────────
    titre reformulé par l'utilisateur  →   recopié tel quel
    note ajoutée par l'utilisateur     →   recopiée telle quelle
    [gen] tableau des champs           →   remplacé par le tableau à jour
      description écrite sous le tableau   récupérée dedans, remise à sa place
    capture collée par l'utilisateur   →   recopiée, image comprise
    [gen] code DAX                     →   remplacé par la formule à jour
    explication de l'utilisateur       →   recopiée, surlignée si le DAX a changé

Un bloc du plan absent du document précédent est ajouté à la fin de l'élément ;
un contenu `gen` dont le bloc n'existe plus dans le plan disparaît.

Ce qui a été écrit *à l'intérieur* d'un contenu du script — sous son tableau,
entre ses valeurs — n'est pas perdu pour autant : `merge.salvage` l'y retrouve
et le repose au même endroit, entre les données remises à jour.
"""

from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from src import console
from src.merge import blocks as block_parser
from src.merge import markers, salvage
from src.merge.blocks import FREE, OWNED, Block, Segment
from src.merge.changes import ChangeLog
from src.merge.previous import CHANGED, NEW, PreviousDocument
from src.merge.transplant import Transplanter

# Nom lisible dans la configuration -> valeur OOXML de `w:highlight`.
_HIGHLIGHTS = {
    "yellow": "yellow",
    "green": "green",
    "turquoise": "cyan",
    "gray": "lightGray",
    "none": None,
}

_PARAGRAPH = qn("w:p")
_HIGHLIGHT = qn("w:highlight")
_STYLE = qn("w:pStyle")


def merge(document, previous: PreviousDocument, options: dict[str, Any], log: ChangeLog) -> None:
    """
    Réécrit le corps du document en superposant le document précédent.

    Le document vient d'être généré : il porte donc déjà toutes les ancres et
    tous les marqueurs. Il est ici recomposé bloc par bloc.
    """
    if not previous.exists:
        return

    nodes = block_parser.body_nodes(document)
    fresh = block_parser.parse(nodes)
    old = block_parser.index(previous.blocks)

    merger = _Merger(document, previous, options, log)
    rebuilt = [node for block in fresh for node in merger.rebuild(block, old.get(block.element_id))]

    body = document.element.body
    for node in nodes:
        body.remove(node)
    for position, node in enumerate(rebuilt):
        body.insert(position, node)


class _Merger:
    def __init__(
        self, document, previous: PreviousDocument, options: dict[str, Any], log: ChangeLog
    ):
        self.transplanter = Transplanter(previous.document, document)
        self.options = options
        self.log = log
        self.keep_user_text = bool(options.get("keep_user_text", True))

    def rebuild(self, fresh: Block, old: Block | None) -> list:
        """Recompose un bloc : ordre de l'utilisateur, contenus du script à jour."""
        nodes = [fresh.anchor] if fresh.anchor is not None else []

        if old is None or not self.keep_user_text:
            # Élément nouveau : tout ce qui vient d'être généré est conservé,
            # y compris les textes d'amorce (titre, « [À compléter] »).
            nodes += [node for segment in fresh.segments for node in segment.nodes]
            self._highlight_new(nodes, fresh)
            return nodes

        generated = {
            segment.block_id: segment.nodes for segment in fresh.segments if segment.kind == OWNED
        }
        emitted: set[str] = set()
        changed = self.log.status_of(fresh.element_id) == CHANGED

        for segment in old.segments:
            if segment.kind == OWNED:
                if segment.block_id in generated and segment.block_id not in emitted:
                    nodes += self._owned(generated[segment.block_id], segment, changed)
                    emitted.add(segment.block_id)
                continue

            nodes += self._preserved(segment.nodes, changed)

        # Blocs ajoutés au plan depuis la version précédente du document.
        for block_id, block_nodes in generated.items():
            if block_id not in emitted:
                nodes += block_nodes

        return nodes

    def _owned(self, fresh: list, old: Segment, changed: bool) -> list:
        """
        Contenu du script remis à jour, autour de ce qu'on a écrit dedans.

        Les données reviennent telles que le script vient de les produire ;
        les contenus rédigés retrouvés à l'intérieur sont reposés au rang
        qu'ils occupaient, entre les mêmes données qu'avant.
        """
        pending: dict[int, list] = {}
        for rank, node in salvage.of(old):
            pending.setdefault(rank, []).append(node)
        if not pending:
            return fresh

        nodes: list = []
        rank = 0
        for node in fresh:
            marker = markers.of(node)
            if marker is None:
                nodes += self._preserved(pending.pop(rank, []), changed)
                rank += 1
            elif marker.kind == markers.GENERATED_END:
                # Ce qui suivait la dernière donnée du script reste à
                # l'intérieur de l'encadrement, donc devant le marqueur de fin.
                nodes += self._preserved(_remaining(pending), changed)
            nodes.append(node)

        return nodes + self._preserved(_remaining(pending), changed)

    def _preserved(self, nodes: list, changed: bool) -> list:
        """Recopie des contenus de l'utilisateur dans le document neuf."""
        copies = []
        for node in nodes:
            copied = self.transplanter.copy(node)
            self._mark_review(copied, changed)
            copies.append(copied)
            self.log.preserved += 1
        return copies

    # ── Signalement visuel ────────────────────────────────────────
    def _mark_review(self, node, changed: bool) -> None:
        """
        Surligne un contenu utilisateur dont l'élément a changé techniquement.

        Le surlignage précédent est retiré d'abord : il portait sur la version
        d'avant et n'a plus lieu d'être si plus rien n'a bougé.
        """
        if node.tag != _PARAGRAPH or _is_heading(node):
            return

        _clear_highlight(node)
        color = _HIGHLIGHTS.get(str(self.options.get("highlight_changed", "yellow")).lower())
        if changed and color is not None:
            _set_highlight(node, color)

    def _highlight_new(self, nodes: list, block: Block) -> None:
        """Signale la zone à rédiger d'un élément apparu depuis la version précédente."""
        if not self.log.is_update or self.log.status_of(block.element_id) != NEW:
            return
        color = _HIGHLIGHTS.get(str(self.options.get("highlight_new", "none")).lower())
        if color is None:
            return
        for segment in block.segments:
            if segment.kind == FREE:
                for node in segment.nodes:
                    if node.tag == _PARAGRAPH and not _is_heading(node):
                        _set_highlight(node, color)


# ─────────────────────────────────────────────────────────────
#  Mise en forme (XML)
# ─────────────────────────────────────────────────────────────


def _remaining(pending: dict[int, list]) -> list:
    """Vide la réserve des contenus pas encore reposés, dans l'ordre des rangs."""
    nodes = [node for rank in sorted(pending) for node in pending[rank]]
    pending.clear()
    return nodes


def _is_heading(paragraph) -> bool:
    """Un titre n'est jamais surligné : il alimente la table des matières."""
    properties = paragraph.find(qn("w:pPr"))
    if properties is None:
        return False
    style = properties.find(_STYLE)
    name = (style.get(qn("w:val")) or "") if style is not None else ""
    return name.lower().startswith(("heading", "titre"))


def _run_properties(run):
    properties = run.find(qn("w:rPr"))
    if properties is None:
        properties = OxmlElement("w:rPr")
        run.insert(0, properties)
    return properties


def _clear_highlight(paragraph) -> None:
    for run in paragraph.iter(qn("w:r")):
        properties = run.find(qn("w:rPr"))
        if properties is None:
            continue
        existing = properties.find(_HIGHLIGHT)
        if existing is not None:
            properties.remove(existing)


def _set_highlight(paragraph, color: str) -> None:
    for run in paragraph.iter(qn("w:r")):
        if not any((text.text or "").strip() for text in run.iter(qn("w:t"))):
            continue
        properties = _run_properties(run)
        if properties.find(_HIGHLIGHT) is None:
            highlight = OxmlElement("w:highlight")
            highlight.set(qn("w:val"), color)
            properties.append(highlight)


def report(log: ChangeLog) -> None:
    console.info(log.summary())
    for line in log.details():
        console.detail(line)
