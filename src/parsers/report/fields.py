"""
Champs de données d'un visuel : projections, étiquettes et filtres.

    visual.query.queryState.<Role>.projections[]   → VisualElement
    visual.objects.referenceLabels[]               → VisualElement
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

# Objets de mise en forme portant des champs : les étiquettes de référence
# d'une carte. Ces champs ne passent pas par `queryState` — ils sont déclarés
# dans l'objet lui-même. Le nom de l'objet est reconnu sur son début, Power BI
# le déclinant selon les versions (`referenceLabels`, `referenceLabel`...).
_REFERENCE_LABELS = "referencelabel"

# Rôles donnés aux champs d'une étiquette de référence. Une étiquette porte une
# valeur, et peut porter un détail sous cette valeur.
REFERENCE_LABEL_VALUE = "ReferenceLabelValue"
REFERENCE_LABEL_DETAIL = "ReferenceLabelDetail"


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
        hierarchy_name=_hierarchy(node) if kind == "HierarchyLevel" else "",
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
        hierarchy = _dig(node, "Expression", "Hierarchy")
        # Hiérarchie de dates : la table est portée par la colonne d'origine ;
        # hiérarchie du modèle : elle est déclarée sur la hiérarchie elle-même.
        node = _dig(hierarchy, "Expression", "PropertyVariationSource") or hierarchy
    return _dig(node, "Expression", "SourceRef").get("Entity", "")


def _hierarchy(node: dict) -> str:
    """
    Hiérarchie dont un `HierarchyLevel` est un niveau.

    Une hiérarchie de dates est engendrée par une colonne (`Date`) : c'est ce
    nom-là que Power BI affiche, plutôt que celui de la hiérarchie technique
    (`Date Hierarchy`). Une hiérarchie du modèle porte son propre nom.
    """
    hierarchy = _dig(node, "Expression", "Hierarchy")
    variation = _dig(hierarchy, "Expression", "PropertyVariationSource")
    return variation.get("Property", "") or hierarchy.get("Hierarchy", "")


def _dig(node: Any, *keys: str) -> dict:
    """Descend une suite de clés imbriquées, en retournant {} au premier trou."""
    for key in keys:
        if not isinstance(node, dict):
            return {}
        node = node.get(key, {})
    return node if isinstance(node, dict) else {}


# ─────────────────────────────────────────────────────────────
#  Étiquettes de référence (cartes)
# ─────────────────────────────────────────────────────────────


def parse_reference_labels(visual_node: dict) -> list[VisualElement]:
    """
    Champs des étiquettes de référence d'une carte.

    Une carte affiche une valeur principale — celle-là passe par `queryState` —
    et peut porter des étiquettes de référence, chacune avec sa valeur et,
    au-dessous, un détail. Ces champs-là sont déclarés dans l'objet de mise en
    forme, pas dans la requête du visuel : sans cette lecture, une mesure qui
    n'apparaît que là passerait pour inutilisée.

    Les noms de propriétés ayant changé d'une version de Power BI à l'autre
    (`valueSource`, `valueText`...), toute propriété portant un champ est
    retenue, et c'est son nom qui range le champ en valeur ou en détail.
    """
    elements: list[VisualElement] = []

    for container in (visual_node.get("objects"), visual_node.get("visualContainerObjects")):
        for name, entries in (container or {}).items():
            if not str(name).lower().startswith(_REFERENCE_LABELS):
                continue
            for entry in entries or []:
                elements.extend(_label_fields(entry))

    return elements


def _label_fields(entry: Any) -> list[VisualElement]:
    """Champs portés par une étiquette, dans l'ordre où elle les déclare."""
    if not isinstance(entry, dict):
        return []

    elements = []
    for name, value in (entry.get("properties") or {}).items():
        field = value.get("expr") if isinstance(value, dict) else None
        kind, node = _field_node(field or {})
        if not kind:
            continue

        property_name = (
            node.get("Level", "") if kind == "HierarchyLevel" else node.get("Property", "")
        )
        role = REFERENCE_LABEL_DETAIL if "detail" in str(name).lower() else REFERENCE_LABEL_VALUE

        elements.append(
            VisualElement(
                query_ref=f"{_entity(node, kind)}.{property_name}".strip("."),
                display_name=property_name or str(name),
                type_category=_CATEGORIES.get(kind, "Inconnu"),
                role=role,
                table_name=_entity(node, kind),
                property_name=property_name,
                hierarchy_name=_hierarchy(node) if kind == "HierarchyLevel" else "",
            )
        )

    return elements


# ─────────────────────────────────────────────────────────────
#  Filtres
# ─────────────────────────────────────────────────────────────


def parse_filters(filters: list) -> list[VisualFilter]:
    """Parse une liste de filtres PBIR. Seuls les filtres actifs sont retournés."""
    parsed = (_parse_filter(item) for item in filters or [])
    return [item for item in parsed if item]


def _parse_filter(item: dict) -> VisualFilter | None:
    """Parse un filtre. Retourne None s'il ne porte aucune condition active."""
    field = item.get("field") or {}
    name = field_name(field)
    measure = _filtered_measure(field)

    for clause in (item.get("filter") or {}).get("Where") or []:
        condition = clause.get("Condition") or {}

        # Exclusion : Not(In(...))
        excluded = _values(_dig(condition, "Not", "Expression", "In").get("Values", []))
        if excluded:
            return VisualFilter(
                field_name=name,
                filter_type="Exclut",
                values=excluded,
                measure_name=measure,
            )

        # Inclusion : In(...)
        included = _values(_dig(condition, "In").get("Values", []))
        if included:
            return VisualFilter(
                field_name=name,
                filter_type="Inclut",
                values=included,
                measure_name=measure,
            )

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
                measure_name=measure,
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


def _filtered_measure(field: dict) -> str:
    """Mesure sur laquelle porte un filtre, ou "" s'il porte sur autre chose."""
    kind, node = _field_node(field)
    return node.get("Property", "") if kind == "Measure" else ""


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
