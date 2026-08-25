"""
Fusion du document fraîchement généré avec le précédent.

Le contrat : le script est propriétaire des contenus qu'il a produits, marqués
`pbi::gen`. Tout le reste appartient à l'utilisateur.

Pour chaque élément documenté, on superpose deux séquences de blocs :

    l'ordre du document précédent    ce que l'utilisateur a voulu
    l'ordre du plan                  ce que le script sait écrire aujourd'hui

Les blocs communs gardent **l'ordre du document** — un remaniement à
l'intérieur d'un élément est respecté. Les blocs que le plan a gagnés depuis
sont insérés **à leur place dans le plan**, entre leurs voisins connus : une
rubrique ajoutée au YAML apparaît donc aussi dans les éléments déjà rédigés.

    ancien bloc                            bloc reconstruit
    ─────────────────────────────────────  ────────────────────────────────
    titre reformulé par l'utilisateur  →   recopié tel quel
    note ajoutée par l'utilisateur     →   recopiée telle quelle
    [gen] tableau des champs           →   remplacé par le tableau à jour
      description écrite sous le tableau   récupérée dedans, remise à sa place
    capture collée par l'utilisateur   →   recopiée, image comprise
    [gen] code DAX                     →   remplacé par la formule à jour
    [seed] zone à compléter rédigée    →   la version du document l'emporte
    [seed] amorce jamais touchée       →   reprise du plan, donc à jour
    explication de l'utilisateur       →   recopiée, surlignée si le DAX a changé

Un contenu `gen` dont le bloc n'existe plus dans le plan n'est pas réécrit,
mais ce que l'utilisateur avait glissé dedans lui est rendu : `merge.salvage`
l'y retrouve et le repose entre les données remises à jour.
"""

from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from src import console
from src.merge import blocks as block_parser
from src.merge import cells, markers, orphans, salvage
from src.merge.blocks import FREE, SEED, Block, Segment
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
_TABLE = qn("w:tbl")
_HIGHLIGHT = qn("w:highlight")
_STYLE = qn("w:pStyle")

# Repère du contenu qui ouvre un bloc — le titre — dans `Block.free_after()`.
_HEAD = ""

# Empreinte d'un contenu vide : une ligne blanche n'est jamais à recueillir.
_EMPTY = markers.fingerprint("")


def merge(
    document,
    previous: PreviousDocument,
    options: dict[str, Any],
    log: ChangeLog,
    styles,
) -> orphans.Collector:
    """
    Réécrit le corps du document en superposant le document précédent.

    Le document vient d'être généré : il porte donc déjà toutes les ancres et
    tous les marqueurs. Il est ici recomposé bloc par bloc, et ce qui n'a pas
    pu être replacé est rassemblé en annexe plutôt que perdu.
    """
    collector = orphans.collector(options)
    if not previous.exists:
        return collector

    fresh = block_parser.parse(block_parser.body_nodes(document))
    old = block_parser.index(previous.blocks)

    for before, after in _renames(fresh, old):
        log.record_rename(before, after)
    before_rename = {after: before for before, after in log.renamed}

    promoted = _promoted_headings(fresh, old) if _predates_seeds(previous.blocks) else {}
    merger = _Merger(document, previous, options, log, collector, promoted)
    rebuilt = [
        node
        for block in fresh
        for node in merger.rebuild(
            block, old.get(before_rename.get(block.element_id, block.element_id))
        )
    ]

    orphans.collect_preamble(collector, previous.blocks, fresh)
    orphans.collect_removed(collector, old, log.written_ids | log.renamed_ids)
    rebuilt += orphans.render(
        document, merger.transplanter, styles, collector, orphans.carried(old)
    )

    # Le corps est vidé de tout ce qu'il porte — y compris les paragraphes que
    # l'annexe vient d'y ajouter — puis reçoit la composition finale, insérée
    # d'un seul geste devant les propriétés de section.
    body = document.element.body
    for node in block_parser.body_nodes(document):
        body.remove(node)
    body[:0] = rebuilt

    return collector


class _Merger:
    def __init__(
        self,
        document,
        previous: PreviousDocument,
        options: dict[str, Any],
        log: ChangeLog,
        collector: orphans.Collector,
        promoted: dict[str, set[str]],
    ):
        self.transplanter = Transplanter(previous.document, document)
        self.log = log
        self.collector = collector
        self.keep_user_text = bool(options.get("keep_user_text", True))
        self._promoted = promoted
        # Réglages de signalement : constants pour toute la fusion.
        self._signal = _colors(options, "highlight_changed", "highlight_new")
        self._changed_color = _color(options, "highlight_changed", "yellow")
        self._new_color = _color(options, "highlight_new", "none")

    # ── Recomposition d'un bloc ───────────────────────────────────
    def rebuild(self, fresh: Block, old: Block | None) -> list:
        """Recompose un bloc : ordre de l'utilisateur, contenus du script à jour."""
        nodes = [fresh.anchor] if fresh.anchor is not None else []

        if old is None or not self.keep_user_text:
            # Élément nouveau : tout ce qui vient d'être généré est conservé,
            # y compris les textes d'amorce (titre, « [À compléter] »).
            nodes += [node for segment in fresh.segments for node in segment.nodes]
            self._highlight_new(nodes, fresh)
            return nodes

        fresh_segments = fresh.identified_segments()
        old_segments = old.identified_segments()
        fresh_free = fresh.free_after()
        old_free = old.free_after()
        changed = self.log.status_of(fresh.element_id) == CHANGED

        element_id = fresh.element_id
        nodes += self._free(element_id, _HEAD, old_free, fresh_free, changed)
        for block_id in _weave(old.block_ids, fresh.block_ids):
            nodes += self._segment(
                fresh_segments.get(block_id), old_segments.get(block_id), changed
            )
            nodes += self._free(element_id, block_id, old_free, fresh_free, changed)

        return nodes

    def _free(
        self,
        element_id: str,
        key: str,
        old_free: dict[str, list],
        fresh_free: dict[str, list],
        changed: bool,
    ) -> list:
        """
        Contenu libre attaché à un bloc : le titre, une note glissée après lui.

        Il n'a pas d'identité propre — c'est le bloc qui le précède qui le
        situe. La version du document l'emporte toujours : c'est celle que
        l'utilisateur a sous les yeux. Le plan ne s'exprime que là où le
        document n'a rien, c'est-à-dire sous un bloc qu'il vient de gagner.
        """
        if key in old_free:
            return self._preserved(self._without_promoted(element_id, old_free[key]), changed)
        return list(fresh_free.get(key, []))

    def _without_promoted(self, element_id: str, nodes: list) -> list:
        """
        Écarte le titre qu'un élément voisin vient de reprendre à son compte.

        Une sous-partie sans `bookmark:` n'était pas ancrée : son titre vivait
        comme contenu libre, à la suite de l'élément précédent. Maintenant
        qu'elle est ancrée, le titre est écrit par son propre bloc — le
        recopier ferait apparaître un doublon, le temps de la génération qui
        suit la mise à jour.

        Le rapprochement est délibérément étroit, et ne vaut que le temps de la
        migration (voir `_predates_seeds`) : seul le titre d'un élément neuf est
        écarté, et seulement du contenu libre de l'élément qui le précède
        immédiatement. Le texte écarté n'est pas perdu pour autant — c'est
        exactement celui que la partie nouvellement ancrée vient d'écrire.
        """
        promoted = self._promoted.get(element_id)
        if not promoted:
            return nodes

        return [
            node for node in nodes if not (_is_heading(node) and markers.digest(node) in promoted)
        ]

    def _segment(self, fresh: Segment | None, old: Segment | None, changed: bool) -> list:
        """Contenu d'un bloc identifié, selon ce que le plan et le document en disent."""
        if fresh is None:
            # Bloc retiré du plan : ses données ne sont plus écrites. Ce qu'on
            # avait glissé dedans revient à sa place ; ce qu'on avait écrit à la
            # place de ses données part en annexe, faute d'un endroit où le
            # reposer — ni l'un ni l'autre n'est jeté.
            return self._dropped(old, changed) if old is not None else []
        if old is None:
            # Bloc gagné par le plan : écrit tel qu'il vient d'être produit.
            return list(fresh.nodes)
        if fresh.kind == SEED:
            return self._seed(fresh, old, changed)

        # Une donnée du script retouchée à la main est réécrite — elle est à
        # lui — mais la version retouchée part en annexe, pas à la corbeille.
        # Un tableau annoté de l'intérieur fait exception : ses annotations
        # retrouvent leur cellule dans le tableau à jour.
        salvaged, retouched = salvage.scan(old)
        self.collector.add(
            "reworked", old.block_id, self._reconcile(fresh.content_nodes(), retouched)
        )
        return self._owned(fresh.nodes, salvaged, changed)

    def _dropped(self, old: Segment, changed: bool) -> list:
        """Ce que l'utilisateur avait écrit dans un bloc que le plan a perdu."""
        salvaged, retouched = salvage.scan(old)
        self.collector.add("dropped", old.block_id, [node for _, node in retouched])
        return self._preserved([node for _, node in salvaged], changed)

    def _reconcile(self, content: list, retouched: list[tuple[int, object]]) -> list:
        """
        Ramène dans le tableau à jour ce qu'on avait écrit dans ses cellules.

        Retourne ce qui reste à recueillir : les données retouchées qui ne sont
        pas des tableaux, et les tableaux dont les annotations n'ont pas pu être
        rattachées à une ligne sûre.

        Le rapprochement se fait par le rang qu'occupait la donnée retouchée
        parmi les contenus du bloc, et non par l'ordre des tableaux : un bloc
        qui en écrit plusieurs verrait sinon l'annotation du second reposée
        dans le premier.
        """
        tables = {rank: node for rank, node in enumerate(content) if node.tag == _TABLE}
        return [
            node
            for rank, node in retouched
            if not (
                node.tag == _TABLE  # type: ignore
                and rank in tables
                and cells.reconcile(node, tables[rank], self.transplanter.copy)
            )
        ]

    def _seed(self, fresh: Segment, old: Segment, changed: bool) -> list:
        """
        Amorce : écrite à la première génération, puis laissée à l'utilisateur.

        Tant qu'elle n'a pas été touchée, c'est la version du plan qui est
        reprise — une formulation améliorée dans le YAML atteint ainsi les
        documents existants. Dès qu'on y a écrit, le document l'emporte, et il
        garde ses propres délimiteurs : eux seuls décrivent ce qu'il contient.
        """
        if old.untouched:
            return list(fresh.nodes)
        return self._preserved(old.nodes, changed)

    def _owned(self, fresh: list, salvaged: list[tuple[int, object]], changed: bool) -> list:
        """
        Contenu du script remis à jour, autour de ce qu'on a écrit dedans.

        Les données reviennent telles que le script vient de les produire ;
        les contenus rédigés retrouvés à l'intérieur sont reposés au rang
        qu'ils occupaient, entre les mêmes données qu'avant.
        """
        pending: dict[int, list] = {}
        for rank, node in salvaged:
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
            elif marker.kind in (markers.GENERATED_END, markers.SEED_END):
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
            if markers.of(node) is None:
                self._mark_review(copied, changed)
                self.log.preserved += 1
            copies.append(copied)
        return copies

    # ── Signalement visuel ────────────────────────────────────────
    def _mark_review(self, node, changed: bool) -> None:
        """
        Surligne un contenu utilisateur dont l'élément a changé techniquement.

        Le surlignage posé par le script est retiré d'abord : il portait sur la
        version d'avant et n'a plus lieu d'être si plus rien n'a bougé. Celui
        que l'utilisateur a posé lui-même est reconnaissable — il ne porte pas
        les couleurs du signalement — et reste en place.
        """
        if node.tag != _PARAGRAPH or _is_heading(node):
            return

        _clear_highlight(node, self._signal)
        if changed and self._changed_color is not None:
            _set_highlight(node, self._changed_color)

    def _highlight_new(self, nodes: list, block: Block) -> None:
        """Signale la zone à rédiger d'un élément apparu depuis la version précédente."""
        if not self.log.is_update or self.log.status_of(block.element_id) != NEW:
            return
        color = self._new_color
        if color is None:
            return
        for segment in block.segments:
            if segment.kind in (FREE, SEED):
                for node in segment.nodes:
                    if (
                        node.tag == _PARAGRAPH
                        and not _is_heading(node)
                        and markers.of(node) is None
                    ):
                        _set_highlight(node, color)


# ─────────────────────────────────────────────────────────────
#  Superposition des deux ordres
# ─────────────────────────────────────────────────────────────


def _weave(old_ids: list[str], fresh_ids: list[str]) -> list[str]:
    """
    Ordre des blocs d'un élément : celui du document, complété par le plan.

    Les blocs que les deux connaissent gardent l'ordre du **document** — c'est
    celui que l'utilisateur a voulu. Ceux que seul le **plan** connaît sont
    insérés derrière le bloc commun qui les précède dans le plan : une rubrique
    ajoutée au YAML retrouve ainsi sa place, et non la fin de l'élément.
    """
    # Un identifiant répété ne désigne qu'un segment : le premier (voir
    # `Block.identified_segments`). Le dédoublonnage a lieu une fois, ici.
    old_ids = list(dict.fromkeys(old_ids))
    fresh_ids = list(dict.fromkeys(fresh_ids))
    common = set(old_ids) & set(fresh_ids)

    # Blocs neufs, rangés derrière le bloc commun qui les précède dans le plan.
    following: dict[str, list[str]] = {}
    previous = _HEAD
    for block_id in fresh_ids:
        if block_id in common:
            previous = block_id
        else:
            following.setdefault(previous, []).append(block_id)

    order = list(following.pop(_HEAD, []))
    for block_id in old_ids:
        order.append(block_id)
        order += following.pop(block_id, [])

    # Blocs neufs dont le voisin de plan a disparu du document : à la suite.
    for remaining in following.values():
        order += remaining
    return order


def _renames(fresh: list[Block], old: dict[str, Block]) -> list[tuple[str, str]]:
    """
    Rapproche un élément apparu d'un élément disparu, par son état technique.

    Renommer une mesure dans Power BI change son identifiant : le document
    voyait une suppression suivie d'un ajout, et la rédaction ne suivait pas.
    Or l'empreinte, elle, ne bouge pas — c'est la même formule DAX. Le
    rapprochement n'est fait que s'il est **sans ambiguïté** : une seule
    disparition et une seule apparition portant cette empreinte.
    """
    present = {block.element_id for block in fresh if block.element_id}
    appeared = _by_fingerprint(
        block for block in fresh if block.element_id and block.element_id not in old
    )
    vanished = _by_fingerprint(
        block for element_id, block in old.items() if element_id not in present
    )

    return [
        (vanished[digest][0].element_id, blocks[0].element_id)
        for digest, blocks in appeared.items()
        if len(blocks) == 1 and len(vanished.get(digest, ())) == 1
    ]


def _by_fingerprint(blocks) -> dict[str, list[Block]]:
    """Blocs regroupés par empreinte technique, celle-ci renseignée."""
    grouped: dict[str, list[Block]] = {}
    for block in blocks:
        if block.fingerprint and block.fingerprint != _EMPTY:
            grouped.setdefault(block.fingerprint, []).append(block)
    return grouped


def _previous_of(block: Block, old: dict[str, Block], log: ChangeLog) -> Block | None:
    """Le bloc du document précédent qui correspond, sous son nom d'alors."""
    before = {after: before for before, after in log.renamed}.get(block.element_id)
    return old.get(before or block.element_id)


def _predates_seeds(blocks: list[Block]) -> bool:
    """
    Le document précédent est-il antérieur aux encadrements d'amorce ?

    Avant eux, une sous-partie sans `bookmark:` n'était pas ancrée et son titre
    vivait comme contenu libre. La reprise de ce titre (voir
    `_promoted_headings`) n'a de sens qu'à cette occasion : un document déjà
    produit par cette version ne doit plus jamais y être soumis.
    """
    return not any(segment.kind == SEED for block in blocks for segment in block.segments)


def _promoted_headings(fresh: list[Block], old: dict[str, Block]) -> dict[str, set[str]]:
    """
    Titres d'éléments neufs, rangés sous l'élément qui les précède.

    Une sous-partie que le plan n'ancrait pas encore voit son titre passer du
    contenu libre à un bloc en propre. Le temps d'une génération, le document
    porte les deux : l'ancien exemplaire traîne à la suite de l'élément
    précédent, où il vivait. Ces empreintes disent lequel écarter, et où.
    """
    promoted: dict[str, set[str]] = {}
    for position, block in enumerate(fresh):
        if not block.element_id or block.element_id in old:
            continue
        before = fresh[position - 1].element_id if position else ""
        if not before or before not in old:
            continue
        promoted.setdefault(before, set()).update(
            markers.digest(node)
            for segment in block.segments
            for node in segment.content_nodes()
            if _is_heading(node)
        )
    return promoted


# ─────────────────────────────────────────────────────────────
#  Mise en forme (XML)
# ─────────────────────────────────────────────────────────────


def _remaining(pending: dict[int, list]) -> list:
    """Vide la réserve des contenus pas encore reposés, dans l'ordre des rangs."""
    nodes = [node for rank in sorted(pending) for node in pending[rank]]
    pending.clear()
    return nodes


def _color(options: dict[str, Any], key: str, fallback: str) -> str | None:
    """Valeur OOXML du surlignage déclaré sous `key`, ou None pour « aucun »."""
    return _HIGHLIGHTS.get(str(options.get(key, fallback)).lower())


def _colors(options: dict[str, Any], *keys: str) -> set[str]:
    """Couleurs que le script emploie pour signaler — les seules qu'il retire."""
    return {color for key in keys if (color := _color(options, key, "")) is not None}


def _is_heading(paragraph) -> bool:
    """Un titre n'est jamais surligné : il alimente la table des matières."""
    if paragraph.tag != _PARAGRAPH:
        return False
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


def _clear_highlight(paragraph, colors: set[str]) -> None:
    for run in paragraph.iter(qn("w:r")):
        properties = run.find(qn("w:rPr"))
        if properties is None:
            continue
        existing = properties.find(_HIGHLIGHT)
        if existing is not None and existing.get(qn("w:val")) in colors:
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
