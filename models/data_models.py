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
class VisualElement:
    """Représente un champ de données utilisé dans un visuel."""

    query_ref: str
    display_name: str
    friendly_name: str
    type_category: str  # "Mesure", "Colonne", "Hiérarchie"
    role: str  # "Values", "Category", "Y", "Y2", etc.
    table_name: str = ""
    display_folder: str = "Racine"


@dataclass
class Visual:
    """Représente un visuel Power BI."""

    id: str
    visual_type: str
    title: str
    elements: list = field(default_factory=list)
    filters: list = field(default_factory=list)
    has_measures: bool = False

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
    filters: list = field(default_factory=list)
    visuals: list = field(default_factory=list)


@dataclass
class PowerBIReport:
    """Représente l'ensemble du rapport Power BI documenté."""

    name: str
    pages: list = field(default_factory=list)
    all_measures: dict = field(default_factory=dict)
    measures_used_in_report: set = field(default_factory=set)
