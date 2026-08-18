"""
Parseur du rapport Power BI en format PBIR.
Structure :
  Report/definition/pages/<hash>/page.json
                                 visuals/<hash>/visual.json

visual.json :
  visual.query.queryState.<Role>.projections[]  → éléments de données
  visual.visualContainerObjects.title[]         → titre
  filterConfig.filters[]                        → filtres déclarés
"""

import json
import os

from src.models.data_models import (
    PowerBIReport,
    ReportPage,
    Visual,
    VisualElement,
    VisualFilter,
)


def parse_report(report_dir: str, report_name: str = "Rapport Power BI") -> PowerBIReport:
    """
    Parse le dossier .Report/ d'un projet .pbip.

    Args:
        report_dir: Chemin vers le dossier .Report/
        report_name: Nom du rapport

    Returns:
        Un objet PowerBIReport
    """
    report = PowerBIReport(name=report_name)

    pages_dir = os.path.join(report_dir, "definition", "pages")
    if not os.path.isdir(pages_dir):
        print(f"  Dossier pages introuvable : '{pages_dir}'")
        return report

    page_order = _load_page_order(pages_dir)

    for folder_name in os.listdir(pages_dir):
        folder_path = os.path.join(pages_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue

        page = _parse_page(folder_path, folder_name, page_order)
        if page:
            report.pages.append(page)

    report.pages.sort(key=lambda p: p.order)

    total_v = sum(len(p.visuals) for p in report.pages)
    doc_v = sum(1 for p in report.pages for v in p.visuals if v.has_measures)
    print(f"  ✓ {len(report.pages)} pages | {total_v} visuels | {doc_v} avec mesures")
    return report


# ─────────────────────────────────────────────────────────────
#  Ordre des pages
# ─────────────────────────────────────────────────────────────


def _load_page_order(pages_dir: str) -> dict[str, int]:
    """Charge l'ordre depuis pages.json → {folder_name: index}."""
    path = os.path.join(pages_dir, "pages.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {name: idx for idx, name in enumerate(data.get("pageOrder", []))}
    except json.JSONDecodeError, OSError:
        return {}


# ─────────────────────────────────────────────────────────────
#  Parsing d'une page
# ─────────────────────────────────────────────────────────────


def _parse_page(page_path: str, folder_name: str, page_order: dict[str, int]) -> ReportPage | None:
    """Parse un dossier de page."""
    page_json = os.path.join(page_path, "page.json")
    if not os.path.isfile(page_json):
        return None

    try:
        with open(page_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"  Erreur lecture '{page_json}': {e}")
        return None

    page = ReportPage(
        name=folder_name,
        display_name=data.get("displayName", folder_name),
        order=page_order.get(folder_name, data.get("ordinal", 999)),  # type: ignore
        is_hidden=str(data.get("visibility", "")).lower().startswith("hidden"),
    )

    page.filters = _parse_filter_list(data.get("filters", []))

    visuals_dir = os.path.join(page_path, "visuals")
    if os.path.isdir(visuals_dir):
        for vf in os.listdir(visuals_dir):
            visual_json = os.path.join(visuals_dir, vf, "visual.json")
            if os.path.isfile(visual_json):
                visual = _parse_visual(visual_json, vf)
                if visual:
                    page.visuals.append(visual)

    return page


# ─────────────────────────────────────────────────────────────
#  Parsing d'un visuel
# ─────────────────────────────────────────────────────────────


def _parse_visual(visual_json_path: str, folder_name: str) -> Visual | None:
    """Parse un visual.json PBIR."""
    try:
        with open(visual_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"    Erreur visuel '{folder_name}': {e}")
        return None

    visual_node = data.get("visual", {})
    visual_type = visual_node.get("visualType", "unknown")

    # Les visuels à ignorer sont définis dans config_doc_pbi.yaml
    # (data.visuals.exclude_types) : ici on parse tout.
    if visual_node.get("visualGroup"):
        return None

    title = _extract_title(visual_node) or f"{visual_type} ({folder_name[:8]})"
    elements = _extract_elements(visual_node.get("query", {}))
    has_measures = any(e.type_category == "Mesure" for e in elements)

    filter_config = data.get("filterConfig", {})
    filters = _parse_filter_list(filter_config.get("filters", []))

    position = data.get("position", {})

    return Visual(
        id=folder_name,
        visual_type=visual_type,
        title=title,
        elements=elements,
        filters=filters,
        has_measures=has_measures,
        pos_x=float(position.get("x", 0) or 0),
        pos_y=float(position.get("y", 0) or 0),
    )


# ─────────────────────────────────────────────────────────────
#  Éléments de données (projections)
# ─────────────────────────────────────────────────────────────


def _extract_elements(query: dict) -> list[VisualElement]:
    """Extrait les éléments depuis visual.query.queryState.<Role>.projections[]."""
    elements = []
    query_state = query.get("queryState", {})

    for role_name, role_data in query_state.items():
        for proj in role_data.get("projections", []):
            el = _parse_projection(proj, role_name)
            if el:
                elements.append(el)

    return elements


def _parse_projection(proj: dict, role: str) -> VisualElement | None:
    """Parse une projection en VisualElement."""
    field = proj.get("field", {})
    query_ref = proj.get("queryRef", "")
    if not query_ref:
        return None

    native_ref = proj.get("nativeQueryRef", "")
    display_override = proj.get("displayName", "")

    type_category = "Inconnu"
    table_name = ""
    prop_name = ""

    if "Measure" in field:
        type_category = "Mesure"
        node = field["Measure"]
        table_name = node.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
        prop_name = node.get("Property", "")

    elif "Column" in field:
        type_category = "Colonne"
        node = field["Column"]
        table_name = node.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
        prop_name = node.get("Property", "")

    elif "HierarchyLevel" in field:
        type_category = "Hiérarchie"
        hl = field["HierarchyLevel"]
        try:
            table_name = hl["Expression"]["Hierarchy"]["Expression"]["PropertyVariationSource"][
                "Expression"
            ]["SourceRef"]["Entity"]
        except KeyError, TypeError:
            table_name = ""
        prop_name = hl.get("Level", "")

    display_name = display_override or native_ref or prop_name or query_ref.split(".")[-1]

    return VisualElement(
        query_ref=query_ref,
        display_name=display_name,
        friendly_name=display_override or display_name,
        type_category=type_category,
        role=role,
        table_name=table_name,
        property_name=prop_name,
    )


# ─────────────────────────────────────────────────────────────
#  Titre du visuel
# ─────────────────────────────────────────────────────────────


def _extract_title(visual_node: dict) -> str | None:
    """Extrait le titre depuis visualContainerObjects.title."""
    try:
        title_list = visual_node.get("visualContainerObjects", {}).get("title", [])
        if title_list:
            value = (
                title_list[0]
                .get("properties", {})
                .get("text", {})
                .get("expr", {})
                .get("Literal", {})
                .get("Value", "")
            )
            if value:
                return value.strip("'\"")
    except AttributeError, IndexError, KeyError:
        pass
    return None


# ─────────────────────────────────────────────────────────────
#  Filtres PBIR
# ─────────────────────────────────────────────────────────────


def _parse_filter_list(filters: list) -> list[VisualFilter]:
    """Parse une liste de filtres PBIR. Ne retourne que les filtres actifs (avec condition)."""
    results = []
    for f in filters:
        result = _parse_single_filter(f)
        if result:
            results.append(result)
    return results


def _parse_single_filter(f: dict) -> VisualFilter | None:
    """Parse un filtre. Retourne None si pas de condition active."""
    field = f.get("field", {})
    field_name = _field_name(field)

    filter_def = f.get("filter", {})
    where_clause = filter_def.get("Where", [])

    if not where_clause:
        return None

    for item in where_clause:
        condition = item.get("Condition", {})

        # Exclusion
        if "Not" in condition:
            inner = condition["Not"].get("Expression", {})
            if "In" in inner:
                values = _extract_values(inner["In"].get("Values", []))
                if values:
                    return VisualFilter(field_name=field_name, filter_type="Exclut", values=values)

        # Inclusion
        if "In" in condition:
            values = _extract_values(condition["In"].get("Values", []))
            if values:
                return VisualFilter(field_name=field_name, filter_type="Inclut", values=values)

        # Comparaison
        if "Comparison" in condition:
            comp = condition["Comparison"]
            op = str(comp.get("ComparisonKind", ""))
            right = str(comp.get("Right", {}).get("Literal", {}).get("Value", "")).strip("'\"")
            if op and right:
                return VisualFilter(
                    field_name=field_name,
                    filter_type="Comparison",
                    values=[right],
                    operator=op,
                )

    return None


def _field_name(field: dict) -> str:
    """Nom lisible d'un champ depuis un objet field."""
    if "Measure" in field:
        m = field["Measure"]
        entity = m.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
        prop = m.get("Property", "")
        return f"{entity}.{prop}" if entity else prop

    if "Column" in field:
        c = field["Column"]
        entity = c.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
        prop = c.get("Property", "")
        return f"{entity}.{prop}" if entity else prop

    if "HierarchyLevel" in field:
        hl = field["HierarchyLevel"]
        level = hl.get("Level", "")
        try:
            hierarchy = hl["Expression"]["Hierarchy"]["Hierarchy"]
            return f"{hierarchy}.{level}"
        except KeyError, TypeError:
            return level

    return "Champ inconnu"


def _extract_values(values_nested: list) -> list[str]:
    """Extrait les valeurs littérales d'une liste imbriquée."""
    flat = []
    for item in values_nested:
        if isinstance(item, list):
            for val in item:
                v = str(val.get("Literal", {}).get("Value", "")).strip("'\"")
                if v:
                    flat.append(v)
        elif isinstance(item, dict):
            v = str(item.get("Literal", {}).get("Value", "")).strip("'\"")
            if v:
                flat.append(v)
    return flat
