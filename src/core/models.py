"""
Les structures de données qui circulent entre les trois modules.

Ce sont ces objets que le plan YAML manipule : `{{ measure.name }}`,
`over: page.visuals`, `{{ table.transformation_steps }}`... Tout attribut
ajouté ici devient donc utilisable dans la configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocLink:
    """Texte pointant vers un signet du document (lien interne)."""

    text: str
    target: str

    def __str__(self) -> str:
        return self.text


# ─────────────────────────────────────────────────────────────
#  Modèle sémantique
# ─────────────────────────────────────────────────────────────


@dataclass
class DaxMeasure:
    """Mesure DAX du modèle sémantique."""

    name: str
    expression: str
    table_name: str
    display_folder: str = "Racine"
    description: str = ""
    format_string: str = ""
    is_hidden: bool = False
    # Renseignés par `apps.extract.dependencies` :
    dependent_measures: set[str] = field(default_factory=set)
    used_columns: set[str] = field(default_factory=set)
    used_by_measures: set[str] = field(default_factory=set)
    # Renseigné par `apps.document.references` : visuels affichant la mesure.
    usages: list[DocLink] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DaxMeasure) and self.name == other.name


@dataclass
class TransformationStep:
    """Étape d'un script Power Query (`let ... in ...`)."""

    name: str
    expression: str  # opération de l'étape, ramenée sur une ligne
    # L'expression telle qu'écrite, indentation et retours à la ligne compris.
    raw_expression: str = ""

    def __str__(self) -> str:
        return f"{self.name} = {self.expression}"


@dataclass
class CalculatedColumn:
    """Colonne calculée d'une table : son nom et son expression DAX."""

    name: str
    expression: str

    def __str__(self) -> str:
        return f"{self.name} = {self.expression}"


@dataclass
class ModelTable:
    """Table du modèle sémantique."""

    name: str
    source: str = ""
    transformation_steps: list[TransformationStep] = field(default_factory=list)
    calculated_columns: list[CalculatedColumn] = field(default_factory=list)
    is_hidden: bool = False
    measures: list[DaxMeasure] = field(default_factory=list)


@dataclass
class MeasureGroup:
    """Regroupement de mesures (par table ou par dossier d'affichage)."""

    name: str
    measures: list[DaxMeasure] = field(default_factory=list)


@dataclass
class SemanticModel:
    """Vue du modèle sémantique exposée au plan de documentation."""

    tables: list[ModelTable] = field(default_factory=list)
    tables_with_measures: list[MeasureGroup] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
#  Rapport
# ─────────────────────────────────────────────────────────────


@dataclass
class VisualElement:
    """Champ de données utilisé dans un visuel."""

    query_ref: str
    display_name: str
    type_category: str  # "Mesure", "Colonne", "Hiérarchie"
    role: str  # "Values", "Category", "Y", "Y2"...
    table_name: str = ""
    # Nom du champ dans le modèle (`Property` du visual.json). Le nom affiché
    # peut être un alias : c'est ce nom-ci qui identifie la mesure.
    property_name: str = ""
    # Hiérarchie dont ce champ est un niveau, pour un `HierarchyLevel` : nom de
    # la colonne d'origine pour une hiérarchie de dates (« Date »), nom de la
    # hiérarchie sinon. Vide pour une mesure ou une colonne.
    hierarchy_name: str = ""

    @property
    def model_name(self) -> str:
        """Nom de la mesure/colonne tel qu'il existe dans le modèle."""
        return self.property_name or self.query_ref.split(".")[-1] or self.display_name


@dataclass
class VisualFilter:
    """Filtre appliqué à un visuel ou à une page."""

    field_name: str
    filter_type: str  # "Inclut", "Exclut", "Comparison"
    values: list[str] = field(default_factory=list)
    operator: str = ""
    # Mesure sur laquelle porte le filtre, telle qu'elle existe dans le modèle.
    # Vide pour un filtre portant sur une colonne. Filtrer sur une mesure est
    # une façon de l'utiliser : c'est ce nom qui l'atteste.
    measure_name: str = ""

    def to_string(self) -> str:
        if self.filter_type == "Comparison":
            return f"{self.field_name} ({self.operator} {', '.join(self.values)})"
        return f"{self.field_name} ({self.filter_type}: {', '.join(self.values)})"


@dataclass
class VisualReference:
    """Ligne du tableau des références d'un visuel."""

    number: str
    kind: str  # "mesure", "colonne", "hierarchie", "filtre"
    name: str
    label: str  # libellé complet, en une seule colonne
    role: str = ""  # rôle traduit, colonne « Rôle » du tableau
    expression: str = ""

    @property
    def value(self) -> str:
        """Colonne « Élément référencé » : le nom, ou l'expression du filtre."""
        return self.expression if self.kind == "filtre" else self.name


@dataclass
class Visual:
    """Visuel d'une page du rapport."""

    id: str
    visual_type: str
    title: str
    elements: list[VisualElement] = field(default_factory=list)
    filters: list[VisualFilter] = field(default_factory=list)
    has_measures: bool = False
    # Place du visuel dans le canevas de la page. Un membre de groupe est
    # ramené au repère de la page dès la lecture, même quand le rapport la
    # déclare depuis le coin de son groupe (`pbi_extractor.report.layout`).
    # C'est elle qui permet de recadrer une capture d'écran sur ce
    # seul visuel (voir `apps.capture`).
    pos_x: float = 0.0
    pos_y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    # Nom technique du conteneur (`name` du visual.json). C'est lui que les
    # `parentGroupName` des autres visuels désignent.
    name: str = ""
    # `parentGroupName` : nom du groupe Power BI qui contient le visuel.
    parent_group_name: str = ""
    # Renseigné par `generators.references` : lignes du tableau des références.
    references: list[VisualReference] = field(default_factory=list)

    @property
    def signature(self) -> str:
        """
        Description stable des champs affichés par le visuel.

        Sert d'empreinte à la régénération : si elle change, la documentation
        rédigée pour ce visuel porte peut-être sur une version périmée.
        """
        return " ".join(
            sorted(f"{element.role}:{element.model_name}" for element in self.elements)
            + sorted(item.to_string() for item in self.filters)
        )


@dataclass
class VisualGroupMember:
    """
    Ligne de la légende d'un groupe.

    La légende fait le lien entre la capture du groupe et son contenu : elle
    liste les visuels documentés du groupe. Ceux que `data.visuals` écarte
    (habillage, boutons, visuels présentés ailleurs) n'y figurent pas.
    """

    number: str
    title: str
    visual_type: str
    group_path: str = ""  # sous-groupe(s) traversé(s), vide si enfant direct

    @property
    def label(self) -> str:
        """Colonne « Élément » : le titre, précédé du sous-groupe s'il y en a un."""
        return f"{self.group_path} › {self.title}" if self.group_path else self.title


@dataclass
class VisualGroup:
    """
    Groupe de visuels d'une page (`visualGroup` d'un `visual.json`).

    Un groupe est documenté comme un tout : une capture, une légende de son
    contenu, puis le détail de chacun de ses visuels documentés. Les
    sous-groupes éventuels sont rattachés à leur groupe racine : la structure
    du document reste page → groupe → visuel.
    """

    id: str
    name: str  # `name` du visual.json — cible des `parentGroupName`
    title: str  # `displayName` du groupe
    group_mode: str = ""  # ScaleMode | ScrollMode
    parent_group_name: str = ""  # groupe parent, pour les groupes imbriqués
    # Place du groupe dans le canevas. Power BI déclare le cadre entier —
    # origine et dimensions —, mais un rapport ancien ou retouché peut n'en
    # donner que l'origine : `apps.capture` retombe alors sur l'étendue des
    # visuels du groupe.
    pos_x: float = 0.0
    pos_y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    # Renseignés par `apps.document.filters` :
    visuals: list[Visual] = field(default_factory=list)  # visuels du groupe
    members: list[VisualGroupMember] = field(default_factory=list)  # légende du groupe
    subgroups: list[VisualGroup] = field(default_factory=list)  # sous-groupes directs

    @property
    def signature(self) -> str:
        """
        Description stable du contenu du groupe.

        Sert d'empreinte à la régénération : si un visuel entre ou sort du
        groupe, la rédaction reprise porte peut-être sur une version périmée.
        """
        return " ".join(sorted(f"{m.title}:{m.visual_type}" for m in self.members))


@dataclass
class ReportPage:
    """Page du rapport."""

    name: str
    display_name: str
    order: int = 0
    is_hidden: bool = False
    # Canevas de la page, dans lequel les visuels sont placés. Power BI le
    # déclare rarement : 1280 × 720 est sa taille par défaut, celle d'un
    # « 16:9 » — et c'est elle que les positions des visuels supposent.
    canvas_width: float = 1280.0
    canvas_height: float = 720.0
    filters: list[VisualFilter] = field(default_factory=list)
    visuals: list[Visual] = field(default_factory=list)
    # Conteneurs de groupe lus par le parseur, puis organisés par
    # `generators.filters` : groupes racines documentés de la page.
    groups: list[VisualGroup] = field(default_factory=list)
    # Visuels documentés n'appartenant à aucun groupe.
    ungrouped_visuals: list[Visual] = field(default_factory=list)


@dataclass
class PowerBIReport:
    """Rapport Power BI documenté, une fois toutes les sources rassemblées."""

    name: str
    pages: list[ReportPage] = field(default_factory=list)
    tables: list[ModelTable] = field(default_factory=list)
    all_measures: dict[str, DaxMeasure] = field(default_factory=dict)
    measures_used_in_report: set[str] = field(default_factory=set)
    # Filtres posés sur le rapport entier (`report.json`), au-dessus des
    # filtres de page et de visuel.
    filters: list[VisualFilter] = field(default_factory=list)
    # Renseigné par `apps.document.context` : mesures du modèle qu'aucun visuel ni
    # aucun filtre n'emploie, et que le document ne documente donc pas.
    undocumented_measures: list[str] = field(default_factory=list)

    @property
    def measures_in_visuals(self) -> set:
        """Mesures directement affichées par un visuel (hors dépendances)."""
        return {
            element.model_name
            for page in self.pages
            for visual in page.visuals
            for element in visual.elements
            if element.type_category == "Mesure"
        }

    @property
    def measures_in_filters(self) -> set:
        """
        Mesures employées comme filtre — de rapport, de page ou de visuel.

        Filtrer sur une mesure est une façon de s'en servir, au même titre que
        l'afficher : sans ce relevé, une mesure qui ne sert qu'à filtrer
        passerait pour inutilisée.
        """
        applied = list(self.filters)
        for page in self.pages:
            applied += page.filters
            for visual in page.visuals:
                applied += visual.filters
        return {item.measure_name for item in applied if item.measure_name}

    @property
    def measures_used(self) -> set:
        """Mesures employées quelque part dans le rapport, hors dépendances."""
        return self.measures_in_visuals | self.measures_in_filters


# ─────────────────────────────────────────────────────────────
#  Ce qui circule entre les modules
# ─────────────────────────────────────────────────────────────


@dataclass
class PowerBiMetadata:
    """
    Tout ce que l'on sait du rapport, d'un bout à l'autre de la génération.

    L'extraction le produit, la capture y ajoute l'inventaire de ses images, le
    document s'en sert : aucun des trois n'a à retourner à la source.
    """

    report: PowerBIReport
    source: Path = Path()
    # {page: {prise: chemin}}, relatifs au dossier du projet — un projet
    # déplacé ne perd pas ses images.
    captures: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def project_dir(self) -> Path:
        """Dossier du projet, où vivent les images et les réponses mémorisées."""
        return self.source.parent

    def capture_of(self, page: str, shot: str) -> str:
        """Chemin de la capture d'une prise, ou chaîne vide s'il n'y en a pas."""
        return (self.captures.get(page) or {}).get(shot, "")
