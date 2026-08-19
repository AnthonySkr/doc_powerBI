"""
Champs de données d'un visuel : projections et filtres du `visual.json`.

    visual.query.queryState.<Role>.projections[]   → VisualElement
    filterConfig.filters[]                         → VisualFilter
"""

from typing import Any

from src.models.data_models import VisualElement, VisualFilter

# Type de champ PBIR -> catégorie affichée dans la documentation.
_CATEGORIES = {
    "Measure": "Mesure",
    "Column": "Colonne",
    "HierarchyLevel": "Hiérarchie",
}


# ─────────────────────────────────────────────────────────────
#  Projections
# ─────────────────────────────────────────────────────────────


def parse_elements(query: dict) -> list[VisualElement]:
    """Extrait les éléments depuis `visual.query.queryState.<Role>.projections[]`."""
    elements = []
    for role, role_data in (query.get("queryState") or {}).items():
        for projection in role_data.get("projections", []):
            element = _parse_projection(projection, role)
            if element:
                elements.append(element)
    return elements


def _parse_projection(projection: dict, role: str) -> VisualElement | None:
    query_ref = projection.get("queryRef", "")
    if not query_ref:
        return None

    kind, node = _field_node(projection.get("field") or {})
    property_name = node.get("Level", "") if kind == "HierarchyLevel" else node.get("Property", "")

    display_name = (
        projection.get("displayName")
        or projection.get("nativeQueryRef")
        or property_name
        or query_ref.split(".")[-1]
    )

    return VisualElement(
        query_ref=query_ref,
        display_name=display_name,
        type_category=_CATEGORIES.get(kind, "Inconnu"),
        role=role,
        table_name=_entity(node, kind),
        property_name=property_name,
    )


def _field_node(field: dict) -> tuple[str, dict]:
    """Type du champ (`Measure`, `Column`, `HierarchyLevel`) et son contenu."""
    for kind in _CATEGORIES:
        node = field.get(kind)
        if isinstance(node, dict):
            return kind, node
    return "", {}


def _entity(node: dict, kind: str) -> str:
    """Table d'origine du champ, telle que déclarée dans le `SourceRef`."""
    if kind == "HierarchyLevel":
        node = _dig(node, "Expression", "Hierarchy", "Expression", "PropertyVariationSource")
    return _dig(node, "Expression", "SourceRef").get("Entity", "")


def _dig(node: Any, *keys: str) -> dict:
    """Descend une suite de clés imbriquées, en retournant {} au premier trou."""
    for key in keys:
        if not isinstance(node, dict):
            return {}
        node = node.get(key, {})
    return node if isinstance(node, dict) else {}


# ─────────────────────────────────────────────────────────────
#  Filtres
# ─────────────────────────────────────────────────────────────


def parse_filters(filters: list) -> list[VisualFilter]:
    """Parse une liste de filtres PBIR. Seuls les filtres actifs sont retournés."""
    parsed = (_parse_filter(item) for item in filters or [])
    return [item for item in parsed if item]


def _parse_filter(item: dict) -> VisualFilter | None:
    """Parse un filtre. Retourne None s'il ne porte aucune condition active."""
    name = field_name(item.get("field") or {})

    for clause in (item.get("filter") or {}).get("Where") or []:
        condition = clause.get("Condition") or {}

        # Exclusion : Not(In(...))
        excluded = _values(_dig(condition, "Not", "Expression", "In").get("Values", []))
        if excluded:
            return VisualFilter(field_name=name, filter_type="Exclut", values=excluded)

        # Inclusion : In(...)
        included = _values(_dig(condition, "In").get("Values", []))
        if included:
            return VisualFilter(field_name=name, filter_type="Inclut", values=included)

        # Comparaison
        comparison = _dig(condition, "Comparison")
        operator = str(comparison.get("ComparisonKind", ""))
        right = str(_dig(comparison, "Right", "Literal").get("Value", "")).strip("'\"")
        if operator and right:
            return VisualFilter(
                field_name=name,
                filter_type="Comparison",
                values=[right],
                operator=operator,
            )

    return None


def field_name(field: dict) -> str:
    """Nom lisible d'un champ : `Table.Colonne`, ou `Hierarchie.Niveau`."""
    kind, node = _field_node(field)
    if not kind:
        return "Champ inconnu"

    if kind == "HierarchyLevel":
        level = node.get("Level", "")
        hierarchy = _dig(node, "Expression", "Hierarchy").get("Hierarchy", "")
        return f"{hierarchy}.{level}" if hierarchy else level

    entity = _entity(node, kind)
    prop = node.get("Property", "")
    return f"{entity}.{prop}" if entity else prop


def _values(nested: list) -> list[str]:
    """Extrait les valeurs littérales d'une liste éventuellement imbriquée."""
    flat: list[str] = []
    for item in nested:
        for entry in item if isinstance(item, list) else [item]:
            if not isinstance(entry, dict):
                continue
            value = str(_dig(entry, "Literal").get("Value", "")).strip("'\"")
            if value:
                flat.append(value)
    return flat
