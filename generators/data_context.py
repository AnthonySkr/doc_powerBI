"""
Construction du contexte de données consommé par le plan YAML.

Applique les filtres/tris déclarés dans `data:` (config_doc_pbi.yaml) et
prépare les collections référencées par les boucles du plan :
    report.pages / page.visuals / visual.references
    model.tables / model.tables_with_measures / table.measures
"""

from typing import Any

from doc_config import DocConfig
from models.data_models import (
    DaxMeasure,
    MeasureGroup,
    ModelTable,
    PowerBIReport,
    ReportPage,
    SemanticModel,
    Visual,
    VisualReference,
)

_KIND_BY_CATEGORY = {
    "Mesure": "mesure",
    "Colonne": "colonne",
    "Hiérarchie": "hierarchie",
}


def build_context(
    report: PowerBIReport,
    all_measures: dict[str, DaxMeasure],
    config: DocConfig,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Assemble le contexte passé au générateur Word."""
    report.pages = _filter_pages(report.pages, config)

    reference_options = (config.section_options("visuels") or {}).get("references", {})
    document_counter = _Counter()

    for page in report.pages:
        page.visuals = _filter_visuals(page.visuals, config)
        page_counter = _Counter()
        for visual in page.visuals:
            counter = _counter_for_scope(
                reference_options.get("numbering", {}).get("scope", "visual"),
                document_counter,
                page_counter,
            )
            visual.references = build_references(visual, reference_options, counter)

    model = _build_model(report, all_measures, config)

    return {
        "report": report,
        "model": model,
        "inputs": inputs,
        "styles": config.styles,
    }


# ─────────────────────────────────────────────────────────────
#  Pages et visuels
# ─────────────────────────────────────────────────────────────


def _filter_pages(pages: list[ReportPage], config: DocConfig) -> list[ReportPage]:
    options = config.data["pages"]
    excluded = {name.lower() for name in options.get("exclude_names") or []}

    kept = [
        page
        for page in pages
        if not (options.get("exclude_hidden") and page.is_hidden)
        and page.display_name.lower() not in excluded
    ]

    if options.get("sort_by") == "name":
        kept.sort(key=lambda p: p.display_name.lower())
    else:
        kept.sort(key=lambda p: p.order)

    return kept


def _filter_visuals(visuals: list[Visual], config: DocConfig) -> list[Visual]:
    options = config.data["visuals"]
    excluded_types = {t.lower() for t in options.get("exclude_types") or []}
    excluded_titles = {t.lower() for t in options.get("exclude_titles") or []}

    kept = [
        visual
        for visual in visuals
        if visual.visual_type.lower() not in excluded_types
        and visual.title.lower() not in excluded_titles
        and (not options.get("only_with_measures") or visual.has_measures)
    ]

    if options.get("sort_by") == "position":
        kept.sort(key=lambda v: (v.pos_y, v.pos_x))
    else:
        kept.sort(key=lambda v: v.title.lower())

    return kept


# ─────────────────────────────────────────────────────────────
#  Références d'un visuel (tableau numéro / libellé)
# ─────────────────────────────────────────────────────────────


class _Counter:
    """Compteur de numérotation des références."""

    def __init__(self) -> None:
        self.value: int | None = None
        self.initial = 1

    def start_at(self, start: int) -> None:
        self.initial = start
        if self.value is None:
            self.value = start

    def next(self) -> int:
        if self.value is None:
            self.value = self.initial
        current = self.value
        self.value += 1
        return current


def _counter_for_scope(scope: str, document: _Counter, page: _Counter) -> _Counter:
    if scope == "document":
        return document
    if scope == "page":
        return page
    return _Counter()  # scope "visual" : numérotation repartant à chaque visuel


def build_references(
    visual: Visual, options: dict[str, Any], counter: _Counter
) -> list[VisualReference]:
    """Construit les lignes du tableau des références d'un visuel."""
    labels = options.get("labels") or {}
    roles = options.get("roles") or {}
    order = options.get("order") or ["mesure", "colonne", "hierarchie", "filtre"]
    number_format = (options.get("numbering") or {}).get("format", "{n}")
    start = (options.get("numbering") or {}).get("start", 1)

    counter.start_at(start)

    by_kind: dict[str, list[VisualReference]] = {kind: [] for kind in order}

    for element in sorted(visual.elements, key=lambda e: (e.role, e.display_name)):
        kind = _KIND_BY_CATEGORY.get(element.type_category, "colonne")
        role = roles.get(element.role, roles.get("defaut", element.role))
        name = (
            element.query_ref.split(".")[-1] if kind == "mesure" else element.display_name
        ) or element.display_name
        label = _format_label(
            labels, kind, name=element.display_name, role=role, expression=element.query_ref
        )
        by_kind.setdefault(kind, []).append(
            VisualReference(
                number="",
                kind=kind,
                name=name,
                label=label,
                role=role,
            )
        )

    for filter_item in sorted(visual.filters, key=lambda f: f.field_name):
        expression = filter_item.to_string()
        by_kind.setdefault("filtre", []).append(
            VisualReference(
                number="",
                kind="filtre",
                name=filter_item.field_name,
                label=_format_label(
                    labels,
                    "filtre",
                    name=filter_item.field_name,
                    role="",
                    expression=expression,
                ),
                expression=expression,
            )
        )

    references: list[VisualReference] = []
    for kind in list(order) + [k for k in by_kind if k not in order]:
        for reference in by_kind.get(kind, []):
            reference.number = number_format.format(n=counter.next())
            references.append(reference)

    return references


def _format_label(labels: dict[str, str], kind: str, name: str, role: str, expression: str) -> str:
    template = labels.get(kind) or labels.get("defaut") or "{name}"
    return template.format(name=name, role=role, expression=expression).strip()


# ─────────────────────────────────────────────────────────────
#  Modèle sémantique (tables et mesures)
# ─────────────────────────────────────────────────────────────


def _build_model(
    report: PowerBIReport, all_measures: dict[str, DaxMeasure], config: DocConfig
) -> SemanticModel:
    tables = _filter_tables(report.tables, config)
    groups = _group_measures(all_measures, report.measures_used_in_report, config, tables)
    return SemanticModel(tables=tables, tables_with_measures=groups)


def _filter_tables(tables: list[ModelTable], config: DocConfig) -> list[ModelTable]:
    options = config.data["tables"]
    excluded = {name.lower() for name in options.get("exclude_names") or []}

    kept = [
        table
        for table in tables
        if not (options.get("exclude_hidden") and table.is_hidden)
        and table.name.lower() not in excluded
    ]

    step_format = options.get("step_format") or "{name}"
    for table in kept:
        table.transformation_steps = [
            _format_step(step, step_format) for step in table.transformation_steps
        ]

    if options.get("sort_by", "name") == "name":
        kept.sort(key=lambda t: t.name.lower())

    return kept


def _format_step(step: Any, step_format: str) -> str:
    """Met en forme une étape Power Query ({"name": ..., "expression": ...})."""
    if isinstance(step, dict):
        return step_format.format(
            name=step.get("name", ""), expression=step.get("expression", "")
        ).strip()
    return str(step)


def _group_measures(
    all_measures: dict[str, DaxMeasure],
    used_in_report: set[str],
    config: DocConfig,
    tables: list[ModelTable],
) -> list[MeasureGroup]:
    options = config.data["measures"]

    selected = [
        measure
        for name, measure in all_measures.items()
        if (options.get("scope") == "all" or name in used_in_report)
        and (options.get("include_hidden") or not measure.is_hidden)
    ]

    if options.get("sort_by", "name") == "name":
        selected.sort(key=lambda m: m.name.lower())

    key = (
        (lambda m: m.display_folder)
        if options.get("group_by") == "display_folder"
        else (lambda m: m.table_name)
    )

    grouped: dict[str, list[DaxMeasure]] = {}
    for measure in selected:
        grouped.setdefault(key(measure), []).append(measure)

    # Les mesures sont aussi rattachées aux tables (partie « Table de données »).
    by_table: dict[str, ModelTable] = {t.name: t for t in tables}
    for measure in selected:
        table = by_table.get(measure.table_name)
        if table is not None:
            table.measures.append(measure)

    return [MeasureGroup(name=name, measures=grouped[name]) for name in sorted(grouped)]
