"""
Le plan du document : son chargement, ses valeurs par défaut, son accès.

Tout ce que le document a de réglable vit dans `config.yaml` — le template, les
styles, ce qui est documenté, le plan lui-même. Le code n'en porte rien, hormis
les valeurs par défaut ci-dessous : toute clé absente du fichier de
l'utilisateur en est complétée, si bien que son fichier n'a besoin de contenir
que ce qu'il change.
"""

from pathlib import Path
from typing import Any

import yaml

from src.core import paths
from src.core.expressions import resolve_options

__all__ = [
    "DEFAULTS",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_OUTPUT_DIR",
    "DocConfig",
    "load_config",
]

# Le plan cherché à côté de l'exécutable, et le dossier créé à côté du `.pbip`.
DEFAULT_CONFIG_PATH = "config.yaml"
DEFAULT_OUTPUT_DIR = "doc"


DEFAULTS: dict[str, Any] = {
    "document": {
        # Conserver les réponses aux questions à côté du document, et les
        # reproposer à la génération suivante.
        "remember_answers": True,
        "answers_file": "reponses_{{ report.name }}.yaml",
        "template": "template-doc-pbib.docx",
        "output_dir": DEFAULT_OUTPUT_DIR,
        "output_name": "documentation_{{ report.name }}.docx",
        "cover": {"placeholder": "", "text": "", "bold": True},
        "header_footer": {"replacements": []},
        "properties": {},
    },
    "styles": {
        "heading_1": "Heading 1",
        "heading_2": "Heading 2",
        "heading_3": "Heading 3",
        "heading_4": "Heading 4",
        "subtitle": "Sous-titre 3",
        "normal": "Normal",
        "bullet": "List Bullet",
        "code": "Code DAX",
        "image": "Image Placeholder",
        "caption": "Legende",
        "todo": "A completer",
        "table": "Tableau Reference",
        "table_data": "Tableau Donnees",
        "ref_header": "Ref Entete",
        "ref_number": "Ref Numero",
        "ref_role": "Ref Role",
        "ref_value": "Ref Valeur",
        "technical_id": "Id technique",
        "fallback": "Normal",
    },
    "rendering": {
        "page_break_before_heading_1": True,
        "image_placeholder": {
            "text_format": "[IMAGE] {description}",
            "caption_format": "Figure {n} — {description}",
            "show_caption": False,
            "numbering": "auto",
            "sequence": "Figure",
            "empty_paragraph_after": True,
            "markers": {
                "shape": "ellipse",
                "size_cm": 0.62,
                "spacing_cm": 0.9,
                "line_cm": 0.9,
                "per_row": 12,
                "fill": "0070C0",
                "text_color": "FFFFFF",
                "font_size_pt": 9,
                "style": "{{ styles.normal }}",
            },
        },
        "user_fill": {
            "placeholder_text": "[À compléter]",
            "hint_format": "[{hint}]",
            "show_placeholder": True,
            "style": "{{ styles.todo }}",
        },
        "table_of_contents": {
            "update": True,
            "update_all_fields": False,
            "update_with_word": False,
            "levels": "",
        },
        "links": {
            "enabled": True,
            "style": "Hyperlink",
            "bookmark_prefix": "",
            "auto": {
                "enabled": True,
                "source": "model.tables_with_measures",
                "target": "measure:{{ measure.name }}",
                "in_code": True,
                "skip_self": True,
                "first_occurrence_only": False,
                "case_sensitive": False,
                "min_length": 2,
                "exclude": [],
            },
        },
        "property": {
            "label_style": "{{ styles.subtitle }}",
            "value_style": "{{ styles.normal }}",
            "fallback_style": "{{ styles.todo }}",
            "empty_paragraph_after": False,
        },
    },
    "data": {
        "pages": {"exclude_hidden": True, "exclude_names": [], "sort_by": "report_order"},
        "visuals": {
            "exclude_types": [],
            "exclude_titles": [],
            "only_with_measures": False,
            "sort_by": "title",
            "groups": {
                "enabled": True,
                "keep_empty": False,
                # Un groupe d'un seul visuel ne mérite pas sa propre partie :
                # son titre et sa légende d'une ligne redisent ce que le visuel
                # dit déjà, au prix d'un niveau de plan de plus.
                "keep_single": False,
                "exclude_titles": [],
                "sort_by": "position",
                "member_sort_by": "position",
            },
        },
        "tables": {
            "exclude_hidden": True,
            "exclude_names": [],
            "sort_by": "name",
            "ignore_sources": [],
            "steps": {
                "exclude_unnamed": True,
                "exclude_names": [],
                "exclude_prefixes": [],
            },
        },
        "measures": {
            "scope": "used_in_report",
            "include_hidden": False,
            "include_referenced": True,
            "group_by": "table",
            "sort_by": "name",
        },
    },
    "merge": {
        "enabled": True,
        "keep_user_text": True,
        "backup": True,
        "backup_dir": ".versions",
        # Aucune mise en forme dans le document : ce qui a été ajouté ou
        # modifié est nommé dans le résumé de fin d'exécution.
        "highlight_changed": "none",
        "highlight_new": "none",
        # Annexe recueillant, en fin de document, ce qui n'a pas pu être
        # replacé : élément disparu du rapport, bloc retiré du plan, donnée du
        # script retouchée à la main. Rien n'est jeté en silence.
        "orphans": {
            "enabled": True,
            "title": "Contenu non replacé",
            "intro": "",
        },
    },
    "inputs": [],
    "sections": [],
}


class DocConfig:
    """Accès typé aux différentes parties du fichier de configuration."""

    def __init__(
        self, raw: dict[str, Any] | None = None, path: str | Path | None = DEFAULT_CONFIG_PATH
    ):
        self.raw = _merge_defaults(raw or {}, DEFAULTS)
        # `None` quand le plan ne vient d'aucun fichier : `Path("")` vaudrait
        # `.`, et ferait passer le dossier courant pour celui du plan.
        self.path = Path(path) if path else None

    # ── Sections principales ──────────────────────────────────────
    @property
    def document(self) -> dict[str, Any]:
        return self.raw["document"]

    @property
    def styles(self) -> dict[str, str]:
        return self.raw["styles"]

    @property
    def rendering(self) -> dict[str, Any]:
        return self.raw["rendering"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def merge(self) -> dict[str, Any]:
        return self.raw["merge"]

    @property
    def inputs(self) -> list[dict[str, Any]]:
        return self.raw["inputs"]

    @property
    def sections(self) -> list[dict[str, Any]]:
        return self.raw["sections"]

    # ── Helpers ───────────────────────────────────────────────────
    def resolve_data(self, context: dict[str, Any]) -> DocConfig:
        """
        Retourne la configuration dont les filtres `data:` sont résolus.

        Ils peuvent ainsi dépendre des réponses au lancement — écarter les
        visuels que l'utilisateur a désignés, par exemple. Le reste de la
        configuration est inchangé.
        """
        raw = {**self.raw, "data": resolve_options(self.data, context)}
        return DocConfig(raw, self.path)

    def find_section(self, section_id: str) -> dict[str, Any] | None:
        """Retourne une section du plan par son id (recherche récursive)."""
        return _find_section(self.sections, section_id)

    def section_options(self, section_id: str) -> dict[str, Any]:
        """Retourne le bloc `options` d'une section, ou {} s'il n'existe pas."""
        section = self.find_section(section_id) or {}
        return section.get("options") or {}


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> DocConfig:
    """Charge le plan YAML, complété de ses valeurs par défaut."""
    found = paths.find(path)
    if not found.is_file():
        raise FileNotFoundError(f"Fichier de configuration introuvable : '{found}'")

    try:
        raw = yaml.safe_load(found.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        # Le fichier est livré en clair et se modifie à la main : une faute de
        # frappe doit se lire, pas remonter en trace d'exception.
        raise ValueError(f"YAML illisible dans '{found}' : {e}") from e
    except OSError as e:
        raise ValueError(f"Configuration illisible : {e}") from e

    if raw is not None and not isinstance(raw, dict):
        raise ValueError(f"Configuration invalide dans '{found}' : un dictionnaire est attendu.")

    return DocConfig(raw or {}, found)


def _merge_defaults(value: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Complète `value` avec `defaults` sans écraser ce qui est renseigné."""
    merged = dict(defaults)
    for key, val in value.items():
        default = defaults.get(key)
        if isinstance(val, dict) and isinstance(default, dict):
            merged[key] = _merge_defaults(val, default)
        else:
            merged[key] = val
    return merged


def _find_section(sections: list[dict[str, Any]], section_id: str) -> dict[str, Any] | None:
    for section in sections:
        if section.get("id") == section_id:
            return section
        found = _find_section(section.get("sections") or [], section_id)
        if found:
            return found
    return None
