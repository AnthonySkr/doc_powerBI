"""
Mise à jour d'une documentation déjà rédigée.

Le document livré est complété à la main : descriptions, sources, parties
laissées à compléter. Le régénérer effacerait ce travail. Ce module compare
donc le document existant à ce que le script produirait aujourd'hui, et ne
reporte que les nouveautés et les changements :

  - un item absent du document (mesure, visuel, page, table) y est inséré ;
  - un bloc piloté par le script (code DAX, tableau des références...) est
    remplacé lorsque le modèle a changé ;
  - le texte rédigé par l'utilisateur n'est jamais réécrit : il est surligné
    et accompagné d'une note, pour qu'il soit relu et confirmé ;
  - un item disparu du rapport est signalé, jamais supprimé.
"""

import copy
import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from src.doc_config import DocConfig, render
from src.generators.docx_index import DocIndex, DocItem, index_document

NEW = "nouveau"
CHANGED = "modifié"
REMOVED = "absent du rapport"


@dataclass
class ItemChange:
    """Différence constatée sur un item entre le document et le modèle."""

    bookmark: str
    title: str
    status: str
    blocks: list[str] = field(default_factory=list)
    kind: str = ""  # « mesure », « visuel », « page »... d'après le signet
    block_labels: dict[str, str] = field(default_factory=dict)

    def changes(self) -> str:
        """Blocs modifiés, sous leur libellé lisible."""
        return ", ".join(self.block_labels.get(block, block) for block in self.blocks)

    def describe(self) -> str:
        detail = f" ({self.changes()})" if self.blocks else ""
        label = f"{self.kind} « {self.title} »" if self.kind else f"« {self.title} »"
        return f"{label} — {self.status}{detail}"


@dataclass
class UpdateReport:
    """Bilan d'une mise à jour."""

    added: list[ItemChange] = field(default_factory=list)
    changed: list[ItemChange] = field(default_factory=list)
    removed: list[ItemChange] = field(default_factory=list)

    notes: int = 0  # notes de suivi ajoutées ou mises à jour

    @property
    def empty(self) -> bool:
        return not (self.added or self.changed or self.removed)

    @property
    def applied(self) -> bool:
        """Vrai si la mise à jour a effectivement modifié le document."""
        return bool(self.added or self.changed or self.notes)

    def lines(self) -> list[str]:
        rows = []
        for label, changes in (
            ("Nouveautés", self.added),
            ("Changements", self.changed),
            ("Disparus", self.removed),
        ):
            if changes:
                rows.append(f"  {label} ({len(changes)}) :")
                rows.extend(f"    - {change.describe()}" for change in changes)
        return rows or ["  Aucun changement : le document est à jour"]


def compare(
    existing: DocIndex,
    fresh: DocIndex,
    review_blocks: set[str],
    todo_style: str = "",
    kinds: dict[str, str] | None = None,
    block_labels: dict[str, str] | None = None,
) -> UpdateReport:
    """
    Compare le document existant au document fraîchement généré.

    Deux contenus n'appartiennent pas au script : ils ne sont donc ni comparés
    ni réécrits.
      - les blocs `review` (la description d'une mesure, par exemple) ;
      - les blocs repliés sur leur texte « à compléter », que le modèle ne
        renseigne pas et que l'utilisateur a pu rédiger.
    """
    report = UpdateReport()
    kinds = kinds or {}
    labels = block_labels or {}

    for bookmark in fresh.order:
        item = fresh.items[bookmark]
        current = existing.get(bookmark)
        kind = kinds.get(bookmark, "")

        if current is None:
            report.added.append(ItemChange(bookmark, item.title, NEW, kind=kind))
            continue

        differences = [
            block_id
            for block_id, block in item.blocks.items()
            if block_id not in review_blocks
            and not _is_placeholder(block, todo_style)
            and _differs(current.blocks.get(block_id), block)
        ]
        if differences:
            report.changed.append(
                ItemChange(
                    bookmark,
                    item.title,
                    CHANGED,
                    sorted(differences),
                    kind=kind,
                    block_labels=labels,
                )
            )

    for bookmark in existing.order:
        if bookmark not in fresh.items:
            item = existing.items[bookmark]
            report.removed.append(ItemChange(bookmark, item.title, REMOVED))

    return report


def _is_placeholder(block, todo_style: str) -> bool:
    """Un bloc écrit dans le style « à compléter » n'apporte aucune donnée."""
    return bool(todo_style) and todo_style in block.styles()


def _differs(current, fresh) -> bool:
    """Un bloc absent du document est considéré comme un changement."""
    if fresh is None:
        return False
    if current is None:
        return True
    return _normalize(current.text) != _normalize(fresh.text)


def _normalize(text: str) -> str:
    """Compare les contenus sans tenir compte des espaces de mise en forme."""
    return "\n".join(line.strip() for line in (text or "").splitlines() if line.strip())


# ─────────────────────────────────────────────────────────────
#  Application des changements
# ─────────────────────────────────────────────────────────────


def update_document(
    existing_doc,
    fresh_doc,
    config: DocConfig,
    context: dict[str, Any],
    heading_styles: dict[str, int],
    tracked_blocks: dict[str, str],
    review_blocks: set[str],
    todo_style: str = "",
    kinds: dict[str, str] | None = None,
    options: dict[str, Any] | None = None,
) -> UpdateReport:
    """
    Reporte dans `existing_doc` les nouveautés et changements de `fresh_doc`.

    Retourne le bilan des différences appliquées.
    """
    options = options or config.rendering.get("update") or {}
    ignored = {style for style in (options.get("ignored_run_styles") or []) if style}
    existing = index_document(existing_doc, heading_styles, tracked_blocks, ignored)
    fresh = index_document(fresh_doc, heading_styles, tracked_blocks, ignored)

    report = compare(existing, fresh, review_blocks, todo_style, kinds, options.get("block_labels"))

    _insert_new_items(existing, fresh, report, existing_doc)
    _replace_changed_blocks(existing, fresh, report)
    report.notes = _mark_items(existing, report, config, context, options, review_blocks)
    _renumber_bookmarks(existing_doc.element.body)

    return report


def _insert_new_items(existing: DocIndex, fresh: DocIndex, report: UpdateReport, doc) -> None:
    """
    Insère les items absents, à leur place dans le plan.

    Un nouvel item est placé juste après l'item qui le précède dans le document
    fraîchement généré : l'ordre du plan est ainsi respecté. Les items contenus
    dans un item déjà inséré (les visuels d'une nouvelle page, par exemple)
    arrivent avec lui.
    """
    added = {change.bookmark for change in report.added}
    if not added:
        return

    inserted: set[int] = set()
    anchor = None

    for bookmark in fresh.order:
        item = fresh.items[bookmark]

        if bookmark not in added:
            current = existing.get(bookmark)
            if current is not None:
                anchor = current.last_element
            continue

        if any(id(element) in inserted for element in item.elements):
            continue  # déjà venu avec son parent

        span = _element_span(item.elements)
        anchor = _insert_after(doc, anchor, [copy.deepcopy(node) for node in span])
        inserted.update(id(element) for element in item.elements)


def _element_span(elements: list[Any]) -> list[Any]:
    """
    Suite complète des éléments d'un item, marqueurs compris.

    Les signets des blocs suivis encadrent les paragraphes : ils sont leurs
    voisins, pas leurs enfants. Les recopier avec l'item est indispensable,
    sinon la mise à jour suivante ne retrouverait plus ses blocs.
    """
    if not elements:
        return []

    span = [elements[0]]
    last = elements[-1]
    for node in elements[0].itersiblings():
        span.append(node)
        if node is last:
            break

    # Les fins de signet du dernier bloc suivent le dernier paragraphe :
    # sans elles, l'item recopié porterait des signets jamais refermés.
    opened = {node.get(qn("w:id")) for node in span if node.tag == qn("w:bookmarkStart")} - {
        node.get(qn("w:id")) for node in span if node.tag == qn("w:bookmarkEnd")
    }

    for node in last.itersiblings():
        if node.tag != qn("w:bookmarkEnd") or node.get(qn("w:id")) not in opened:
            break
        span.append(node)
        opened.discard(node.get(qn("w:id")))

    return span


def _insert_after(doc, anchor, elements: list[Any]):
    """Insère des éléments après `anchor`, ou en fin de document."""
    body = doc.element.body
    for element in elements:
        if anchor is None:
            section_properties = body.find(qn("w:sectPr"))
            if section_properties is not None:
                section_properties.addprevious(element)
            else:
                body.append(element)
        else:
            anchor.addnext(element)
        anchor = element
    return anchor


def _replace_changed_blocks(existing: DocIndex, fresh: DocIndex, report: UpdateReport) -> None:
    """Remplace le contenu des blocs pilotés par le script qui ont changé."""
    for change in report.changed:
        current = existing.get(change.bookmark)
        updated = fresh.get(change.bookmark)
        if current is None or updated is None:
            continue

        for block_id in change.blocks:
            target = current.blocks.get(block_id)
            source = updated.blocks.get(block_id)
            if target is None or source is None or not target.elements:
                continue

            first = target.elements[0]
            for element in source.elements:
                first.addprevious(copy.deepcopy(element))
            for element in target.elements:
                element.getparent().remove(element)
            target.elements = []


def _mark_items(
    existing: DocIndex,
    report: UpdateReport,
    config: DocConfig,
    context: dict[str, Any],
    options: dict[str, Any],
    review_blocks: set[str],
) -> int:
    """Surligne les textes à relire et ajoute les notes de suivi."""
    notes = options.get("notes") or {}
    highlight = options.get("highlight", "red")
    style = options.get("note_style_id") or "Normal"
    today = date.today().strftime("%d/%m/%Y")
    written = 0

    for change in report.changed:
        item = existing.get(change.bookmark)
        if item is None:
            continue

        anchor = item.heading
        for block_id in review_blocks:
            block = item.blocks.get(block_id)
            if block and block.elements:
                for element in block.elements:
                    _highlight(element, highlight)
                anchor = block.elements[-1]

        text = render(notes.get("changed"), context)
        if text:
            written += _add_note(
                anchor,
                text.format(date=today, changes=change.changes()),
                style,
                highlight,
                change.bookmark,
            )

    for change in report.removed:
        item = existing.get(change.bookmark)
        text = render(notes.get("removed"), context)
        if item is not None and text:
            written += _add_note(
                item.heading, text.format(date=today), style, highlight, change.bookmark
            )

    return written


def _add_note(anchor, text: str, style: str, highlight: str, bookmark: str) -> int:
    """
    Ajoute une note après un élément, sans jamais la dupliquer.

    La note porte un signet : une exécution suivante la retrouve et la remplace
    au lieu d'en empiler une deuxième. Une note identique est laissée telle
    quelle — elle reste tant que l'utilisateur ne l'a pas supprimée, c'est lui
    qui décide que la relecture est faite.

    Returns:
        1 si le document a été modifié, 0 sinon.
    """
    name = _note_bookmark(bookmark)

    for element in anchor.itersiblings():
        if element.tag != qn("w:p"):
            continue
        if not any(
            start.get(qn("w:name")) == name for start in element.iter(qn("w:bookmarkStart"))
        ):
            continue
        existing_text = "".join(node.text or "" for node in element.iter(qn("w:t")))
        if existing_text == text:
            return 0
        element.getparent().remove(element)
        break

    paragraph = OxmlElement("w:p")
    properties = OxmlElement("w:pPr")
    paragraph_style = OxmlElement("w:pStyle")
    paragraph_style.set(qn("w:val"), style)
    properties.append(paragraph_style)
    paragraph.append(properties)

    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), "0")
    start.set(qn("w:name"), name)
    paragraph.append(start)

    run = OxmlElement("w:r")
    run_properties = OxmlElement("w:rPr")
    if highlight:
        marker = OxmlElement("w:highlight")
        marker.set(qn("w:val"), highlight)
        run_properties.append(marker)
    bold = OxmlElement("w:b")
    run_properties.append(bold)
    run.append(run_properties)
    text_element = OxmlElement("w:t")
    text_element.set(qn("xml:space"), "preserve")
    text_element.text = text
    run.append(text_element)
    paragraph.append(run)

    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), "0")
    paragraph.append(end)

    anchor.addnext(paragraph)
    return 1


def _note_bookmark(bookmark: str) -> str:
    """Nom de signet d'une note de suivi, stable d'une exécution à l'autre."""
    digest = hashlib.md5(bookmark.encode("utf-8")).hexdigest()[:8]
    return f"note_{digest}"


def _highlight(element, color: str) -> None:
    """Surligne tout le texte d'un élément."""
    if not color:
        return
    for run in element.iter(qn("w:r")):
        if run.find(qn("w:t")) is None:
            continue
        properties = run.find(qn("w:rPr"))
        if properties is None:
            properties = OxmlElement("w:rPr")
            run.insert(0, properties)
        marker = properties.find(qn("w:highlight"))
        if marker is None:
            marker = OxmlElement("w:highlight")
            properties.append(marker)
        marker.set(qn("w:val"), color)


def _renumber_bookmarks(body) -> None:
    """
    Renumérote les signets du document.

    Les éléments recopiés depuis le document fraîchement généré apportent
    leurs identifiants : sans renumérotation, deux signets porteraient le même
    et Word considérerait le fichier comme corrompu.
    """
    next_id = 0
    pending: dict[str, list[str]] = {}

    for element in body.iter(qn("w:bookmarkStart"), qn("w:bookmarkEnd")):
        old = element.get(qn("w:id"))
        if element.tag == qn("w:bookmarkStart"):
            next_id += 1
            new = str(next_id)
            element.set(qn("w:id"), new)
            pending.setdefault(old, []).append(new)
        else:
            queue = pending.get(old)
            if queue:
                element.set(qn("w:id"), queue.pop())


def backup_document(path: str, suffix: str = ".bak") -> str | None:
    """Copie de sauvegarde du document avant sa mise à jour."""
    target = path.replace(".docx", f"{suffix}.docx")
    try:
        shutil.copy2(path, target)
    except OSError as e:
        print(f"  Sauvegarde impossible ({e})")
        return None
    return target


def collect_items(index: DocIndex) -> list[DocItem]:
    """Items d'un index, dans l'ordre du document."""
    return [index.items[bookmark] for bookmark in index.order]
