"""
Tableaux numérotés des visuels, et chemin inverse (« utilisée dans »).

Chaque visuel documenté est accompagné d'un tableau numérotant les champs qu'il
affiche, et chaque groupe d'une légende numérotant les visuels qu'il contient —
dans les deux cas, le numéro est reporté à la main sur la capture.
Symétriquement, chaque mesure liste les visuels qui l'emploient.

Les libellés, rôles traduits et gabarits de numérotation sont déclarés dans le
plan, sous `options:` de la section des visuels.
"""

from typing import Any

from src.config import DocConfig, render
from src.models.data_models import (
    DaxMeasure,
    DocLink,
    PowerBIReport,
    Visual,
    VisualElement,
    VisualReference,
)

# Section du plan portant les options de numérotation et de libellés. Le
# générateur n'a pas d'autre attache à un identifiant de section.
VISUALS_SECTION_ID = "visuels"

_KIND_BY_CATEGORY = {
    "Mesure": "mesure",
    "Colonne": "colonne",
    "Hiérarchie": "hierarchie",
}

_DEFAULT_ORDER = ("mesure", "colonne", "hierarchie", "filtre")

# Regroupement des niveaux d'une hiérarchie posée sur un même rôle.
_DEFAULT_HIERARCHY_FORMAT = "{hierarchy} ({levels})"
_DEFAULT_LEVEL_SEPARATOR = " > "


def visual_options(config: DocConfig) -> dict[str, Any]:
    """Options de la section des visuels (`references:` et `usages:`)."""
    return config.section_options(VISUALS_SECTION_ID)


def index_references(report: PowerBIReport, options: dict[str, Any]) -> None:
    """Construit `visual.references` pour tous les visuels du rapport."""
    references = options.get("references") or {}
    numbering = references.get("numbering") or {}
    scope = numbering.get("scope", "visual")
    start = int(numbering.get("start", 1))

    document_counter = _Counter(start)

    for page in report.pages:
        page_counter = _Counter(start)
        for visual in page.visuals:
            counter = {"document": document_counter, "page": page_counter}.get(
                scope, _Counter(start)
            )
            visual.references = build_references(visual, references, counter)


def index_group_members(report: PowerBIReport, options: dict[str, Any]) -> None:
    """
    Numérote la légende de chaque groupe de visuels.

    La légende est la table de correspondance entre la capture du groupe et
    son contenu : elle porte les mêmes numéros que ceux reportés sur l'image.
    """
    numbering = (options.get("groups") or {}).get("numbering") or {}
    scope = numbering.get("scope", "group")
    start = int(numbering.get("start", 1))
    number_format = numbering.get("format", "{n}")

    document_counter = _Counter(start)

    for page in report.pages:
        page_counter = _Counter(start)
        for group in page.groups:
            counter = {"document": document_counter, "page": page_counter}.get(
                scope, _Counter(start)
            )
            for member in group.members:
                member.number = number_format.format(n=counter.next())


def index_usages(
    report: PowerBIReport, all_measures: dict[str, DaxMeasure], options: dict[str, Any]
) -> None:
    """
    Renseigne `measure.usages` : les visuels où chaque mesure est utilisée.

    C'est le chemin inverse des liens vers les définitions — depuis la
    définition d'une mesure, on remonte aux visuels qui l'affichent.
    """
    usages = options.get("usages") or {}
    target_template = usages.get("target") or "visual:{{ page.name }}:{{ visual.id }}"
    label_template = usages.get("label") or "{{ page.display_name }} — {{ visual.title }}"

    for measure in all_measures.values():
        measure.usages = []

    for page in report.pages:
        for visual in page.visuals:
            context = {"page": page, "visual": visual}
            link = DocLink(
                text=render(label_template, context), target=render(target_template, context)
            )
            for name in sorted(_measure_names(visual)):
                measure = all_measures.get(name)
                if measure is not None and not any(
                    usage.target == link.target for usage in measure.usages
                ):
                    measure.usages.append(link)


def build_references(
    visual: Visual, options: dict[str, Any], counter: _Counter
) -> list[VisualReference]:
    """Construit les lignes du tableau des références d'un visuel."""
    labels = options.get("labels") or {}
    roles = options.get("roles") or {}
    order = list(options.get("order") or _DEFAULT_ORDER)
    number_format = (options.get("numbering") or {}).get("format", "{n}")
    hierarchies = options.get("hierarchies") or {}

    by_kind: dict[str, list[VisualReference]] = {kind: [] for kind in order}

    levels = _group_levels(visual.elements, hierarchies)
    for members in sorted(levels, key=lambda m: (m[0].role, m[0].display_name)):
        element = members[0]
        kind = _KIND_BY_CATEGORY.get(element.type_category, "colonne")
        role = roles.get(element.role, roles.get("defaut", element.role))
        name = _reference_name(members, kind, hierarchies)
        # Le nom affiché dans le visuel peut être un alias ; pour une hiérarchie
        # rassemblée, c'est le libellé composé qui la désigne.
        display = name if len(members) > 1 else element.display_name
        by_kind.setdefault(kind, []).append(
            VisualReference(
                number="",
                kind=kind,
                name=name,
                role=role,
                label=_label(labels, kind, name, role, element.query_ref, display),
            )
        )

    filter_role = roles.get("filtre", labels.get("filtre_role", "Filtre"))
    for item in sorted(visual.filters, key=lambda f: f.field_name):
        expression = item.to_string()
        by_kind.setdefault("filtre", []).append(
            VisualReference(
                number="",
                kind="filtre",
                name=item.field_name,
                role=filter_role,
                label=_label(
                    labels, "filtre", item.field_name, filter_role, expression, item.field_name
                ),
                expression=expression,
            )
        )

    references: list[VisualReference] = []
    for kind in order + [kind for kind in by_kind if kind not in order]:
        for reference in by_kind.get(kind, []):
            reference.number = number_format.format(n=counter.next())
            references.append(reference)

    return references


class _Counter:
    """Numérotation continue des références sur une portée donnée."""

    def __init__(self, start: int = 1):
        self.value = start

    def next(self) -> int:
        current = self.value
        self.value += 1
        return current


def _group_levels(
    elements: list[VisualElement], options: dict[str, Any]
) -> list[list[VisualElement]]:
    """
    Réunit les niveaux d'une même hiérarchie affichés sur un même rôle.

    Une hiérarchie de dates posée sur un axe est projetée niveau par niveau —
    Année, Trimestre, Mois… — et remplirait autant de lignes du tableau des
    références. Le lecteur, lui, ne voit qu'un champ : ces niveaux sont donc
    ramenés à une seule référence, dans l'ordre de forage du visuel.

    Les autres champs, et les niveaux d'une hiérarchie portée par un rôle
    différent, restent chacun dans leur groupe d'un seul élément.
    """
    if not options.get("group", True):
        return [[element] for element in elements]

    groups: dict[tuple[str, str, str], list[VisualElement]] = {}
    result: list[list[VisualElement]] = []

    for element in elements:
        key = _hierarchy_key(element)
        members = groups.get(key) if key else None
        if members is None:
            members = [element]
            result.append(members)
            if key:
                groups[key] = members
        else:
            members.append(element)

    return result


def _hierarchy_key(element: VisualElement) -> tuple[str, str, str] | None:
    """Hiérarchie à laquelle rattacher un niveau, ou None si le champ n'en est pas un."""
    if element.type_category != "Hiérarchie" or not element.hierarchy_name:
        return None
    return (element.role, element.table_name, element.hierarchy_name)


def _reference_name(members: list[VisualElement], kind: str, options: dict[str, Any]) -> str:
    """Nom porté par la ligne du tableau, pour un champ seul ou une hiérarchie."""
    element = members[0]
    if kind == "mesure":
        # Le libellé reprend le nom du modèle pour les mesures : c'est lui qui
        # correspond au titre de la définition, donc à la cible du lien.
        return element.model_name or element.display_name
    if len(members) == 1:
        return element.display_name or element.model_name

    separator = options.get("separator", _DEFAULT_LEVEL_SEPARATOR)
    template = options.get("format") or _DEFAULT_HIERARCHY_FORMAT
    levels = separator.join(member.property_name or member.display_name for member in members)
    return template.format(hierarchy=element.hierarchy_name, levels=levels)


def _measure_names(visual: Visual) -> set[str]:
    return {e.model_name for e in visual.elements if e.type_category == "Mesure"}


def _label(
    labels: dict[str, str], kind: str, name: str, role: str, expression: str, display: str
) -> str:
    """
    Met en forme le libellé d'une référence.

    `{name}` est le nom du modèle (celui qui porte le lien vers la définition),
    `{display}` le nom affiché dans le visuel, qui peut être un alias.
    """
    template = labels.get(kind) or labels.get("defaut") or "{name}"
    return template.format(
        name=name, role=role, expression=expression, display=display or name
    ).strip()
