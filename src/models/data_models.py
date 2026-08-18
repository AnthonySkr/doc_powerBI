from dataclasses import dataclass, field


@dataclass
class DaxMeasure:
    """Représente une mesure DAX du modèle sémantique."""

    name: str
    expression: str
    table_name: str
    display_folder: str = "Racine"
    description: str = ""
    format_string: str = ""
    is_hidden: bool = False
    dependent_measures: set = field(default_factory=set)
    used_columns: set = field(default_factory=set)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, DaxMeasure):
            return self.name == other.name
        return False


@dataclass
class VisualFilter:
    """Représente un filtre appliqué à un visuel ou une page."""

    field_name: str
    filter_type: str  # "Inclut", "Exclut", "Comparison"
    values: list = field(default_factory=list)
    operator: str = ""

    def to_string(self) -> str:
        if self.filter_type == "Comparison":
            return f"{self.field_name} ({self.operator} {', '.join(self.values)})"
        return f"{self.field_name} ({self.filter_type}: {', '.join(self.values)})"


@dataclass
class ModelTable:
    """Représente une table du modèle sémantique."""

    name: str
    source: str = ""
    transformation_steps: list = field(default_factory=list)
    is_hidden: bool = False
    measures: list = field(default_factory=list)


@dataclass
class VisualReference:
    """Ligne du tableau des références d'un visuel (numéro + libellé)."""

    number: str
    kind: str  # "mesure", "colonne", "hierarchie", "filtre"
    name: str
    label: str
    role: str = ""
    expression: str = ""


@dataclass
class MeasureGroup:
    """Regroupement de mesures (par table ou par dossier d'affichage)."""

    name: str
    measures: list = field(default_factory=list)


@dataclass
class SemanticModel:
    """Vue du modèle sémantique exposée au plan de documentation."""

    tables: list = field(default_factory=list)
    tables_with_measures: list = field(default_factory=list)


@dataclass
class VisualElement:
    """Représente un champ de données utilisé dans un visuel."""

    query_ref: str
    display_name: str
    friendly_name: str
    type_category: str  # "Mesure", "Colonne", "Hiérarchie"
    role: str  # "Values", "Category", "Y", "Y2", etc.
    table_name: str = ""
    display_folder: str = "Racine"
    # Nom du champ dans le modèle (`Property` du visual.json). Le nom affiché
    # peut être un alias : c'est ce nom-ci qui identifie la mesure.
    property_name: str = ""

    @property
    def model_name(self) -> str:
        """Nom de la mesure/colonne tel qu'il existe dans le modèle."""
        return self.property_name or self.query_ref.split(".")[-1] or self.display_name


@dataclass
class Visual:
    """Représente un visuel Power BI."""

    id: str
    visual_type: str
    title: str
    elements: list = field(default_factory=list)
    filters: list = field(default_factory=list)
    has_measures: bool = False
    pos_x: float = 0.0
    pos_y: float = 0.0
    references: list = field(default_factory=list)

    @property
    def measures(self) -> list:
        return [e for e in self.elements if e.type_category == "Mesure"]

    @property
    def columns(self) -> list:
        return [e for e in self.elements if e.type_category == "Colonne"]


@dataclass
class ReportPage:
    """Représente une page du rapport Power BI."""

    name: str
    display_name: str
    order: int = 0
    is_hidden: bool = False
    filters: list = field(default_factory=list)
    visuals: list = field(default_factory=list)


@dataclass
class PowerBIReport:
    """Représente l'ensemble du rapport Power BI documenté."""

    name: str
    pages: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    all_measures: dict = field(default_factory=dict)
    measures_used_in_report: set = field(default_factory=set)
