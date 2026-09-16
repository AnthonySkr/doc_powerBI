"""
Tableaux numérotés des visuels, et chemin inverse (« utilisée dans »).

Chaque visuel documenté est accompagné d'un tableau numérotant les champs qu'il
affiche, et chaque groupe d'une légende numérotant les visuels qu'il contient —
dans les deux cas, le numéro est reporté à la main sur l'image. Symétriquement,
chaque mesure liste les visuels qui l'emploient.

Les libellés, rôles traduits et gabarits de numérotation sont déclarés dans le
plan, sous `options:` de la section des visuels.
"""

from typing import Any

from src.core.config import DocConfig
from src.core.expressions import render
from src.core.models import (
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
    numbering = _Numbering(references.get("numbering"), default_scope="visual")

    for page in report.pages:
        numbering.open_page()
        for visual in page.visuals:
            visual.references = build_references(visual, references, numbering.counter())


def index_group_members(report: PowerBIReport, options: dict[str, Any]) -> None:
    """
    Numérote la légende de chaque groupe de visuels.

    La légende relie l'image du groupe à son contenu : elle porte les mêmes
    numéros que ceux reportés sur l'image.
    """
    numbering = _Numbering((options.get("groups") or {}).get("numbering"), default_scope="group")

    for page in report.pages:
        numbering.open_page()
        for group in page.groups:
            counter = numbering.counter()
            for member in group.members:
                member.number = numbering.format(counter.next())


def index_usages(
    report: PowerBIReport, all_measures: dict[str, DaxMeasure], options: dict[str, Any]
) -> None:
    """
    Renseigne `measure.usages` : les visuels où chaque mesure est employée.

    C'est le chemin inverse des liens vers les définitions : depuis la
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
                label=_label(
                    labels,
                    kind,
                    name=name,
                    role=role,
                    expression=element.query_ref,
                    display=display or name,
                ),
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
                    labels,
                    "filtre",
                    name=item.field_name,
                    role=filter_role,
                    expression=expression,
                    display=item.field_name,
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
    """Une suite de numéros, distribués un à un."""

    def __init__(self, start: int = 1):
        self.value = start

    def next(self) -> int:
        """Le numéro suivant."""
        current = self.value
        self.value += 1
        return current


class _Numbering:
    """
    Distribue les compteurs selon la portée déclarée par le plan.

    `scope: document` numérote d'un bout à l'autre, `page` repart à chaque
    page, et toute autre valeur repart à chaque élément.
    """

    def __init__(self, options: dict[str, Any] | None, default_scope: str):
        options = options or {}
        self.start = int(options.get("start", 1))
        self.scope = options.get("scope", default_scope)
        self.template = options.get("format", "{n}")
        self._document = _Counter(self.start)
        self._page = _Counter(self.start)

    def open_page(self) -> None:
        """Ouvre une page : le compteur de portée « page » repart du début."""
        self._page = _Counter(self.start)

    def counter(self) -> _Counter:
        """Compteur à employer pour l'élément courant."""
        return {"document": self._document, "page": self._page}.get(
            self.scope, _Counter(self.start)
        )

    def format(self, number: int) -> str:
        """Met le numéro en forme selon le gabarit du plan."""
        return self.template.format(n=number)


def _group_levels(
    elements: list[VisualElement], options: dict[str, Any]
) -> list[list[VisualElement]]:
    """
    Réunit les niveaux d'une même hiérarchie affichés sur un même rôle.

    Une hiérarchie de dates posée sur un axe est projetée niveau par niveau —
    Année, Trimestre, Mois… — et remplirait autant de lignes du tableau. Le
    lecteur, lui, ne voit qu'un champ : ces niveaux tiennent donc une seule
    référence. Tout le reste garde son groupe d'un seul élément.
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
    """Hiérarchie à laquelle rattacher un niveau, ou None si c'est un champ."""
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
    """Noms de modèle des mesures affichées par le visuel."""
    return {e.model_name for e in visual.elements if e.type_category == "Mesure"}


def _label(labels: dict[str, str], kind: str, **values: str) -> str:
    """
    Met en forme le libellé d'une référence.

    Args:
        labels: les gabarits déclarés sous `labels:`.
        kind: `mesure`, `colonne`, `hierarchie` ou `filtre`.
        **values: ce qu'un gabarit peut citer — `{name}` (le nom du modèle,
            celui qui porte le lien), `{display}` (le nom affiché, parfois un
            alias), `{role}` et `{expression}`.
    """
    template = labels.get(kind) or labels.get("defaut") or "{name}"
    return template.format(**values).strip()
