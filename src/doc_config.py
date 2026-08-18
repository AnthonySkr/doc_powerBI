"""
Chargement et interprétation de config_doc_pbi.yaml.

Le fichier YAML décrit la structure du document. Ce module fournit :
  - le chargement avec valeurs par défaut (`load_config`)
  - la substitution des variables `{{ ... }}` (`render`)
  - l'évaluation des conditions `when` (`evaluate`)
"""

import os
import re
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = "config_doc_pbi.yaml"

_VAR_PATTERN = re.compile(r"\{\{\s*(.+?)\s*\}\}")

# Valeurs utilisées lorsque la clé est absente du fichier de configuration.
_DEFAULTS: dict[str, Any] = {
    "document": {
        "template": "template-doc-pbib-v2.docx",
        "output_dir": "output",
        "output_name": "documentation_{{ report.name }}.docx",
        "write_mode": "append",
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
            "numbering": True,
            "empty_paragraph_after": True,
        },
        "user_fill": {
            "placeholder_text": "[À compléter]",
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
        },
        "tables": {
            "exclude_hidden": True,
            "exclude_names": [],
            "sort_by": "name",
            "step_format": "{name}",
        },
        "measures": {
            "scope": "used_in_report",
            "include_hidden": False,
            "include_referenced": True,
            "group_by": "table",
            "sort_by": "name",
        },
    },
    "inputs": [],
    "sections": [],
}


class DocConfig:
    """Accès typé aux différentes parties du fichier de configuration."""

    def __init__(self, raw: dict[str, Any], path: str = DEFAULT_CONFIG_PATH):
        self.raw = _merge_defaults(raw or {}, _DEFAULTS)
        self.path = path

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
    def inputs(self) -> list[dict[str, Any]]:
        return self.raw["inputs"]

    @property
    def sections(self) -> list[dict[str, Any]]:
        return self.raw["sections"]

    # ── Helpers ───────────────────────────────────────────────────
    def find_section(self, section_id: str) -> dict[str, Any] | None:
        """Retourne une section du plan par son id (recherche récursive)."""
        return _find_section(self.sections, section_id)

    def section_options(self, section_id: str) -> dict[str, Any]:
        """Retourne le bloc `options` d'une section, ou {} s'il n'existe pas."""
        section = self.find_section(section_id)
        if not section:
            return {}
        return section.get("options") or {}


def load_config(path: str = DEFAULT_CONFIG_PATH) -> DocConfig:
    """Charge le fichier YAML de configuration."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Fichier de configuration introuvable : '{path}'")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is not None and not isinstance(raw, dict):
        raise ValueError(f"Configuration invalide dans '{path}' : un dictionnaire est attendu.")

    return DocConfig(raw or {}, path)


# ─────────────────────────────────────────────────────────────
#  Substitution des variables {{ ... }}
# ─────────────────────────────────────────────────────────────


def render(value: Any, context: dict[str, Any]) -> str:
    """Remplace les `{{ expression }}` d'une chaîne par leur valeur."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)

    def replace(match: re.Match) -> str:
        return _to_text(resolve(match.group(1), context))

    return _VAR_PATTERN.sub(replace, value).strip()


def render_list(value: Any, context: dict[str, Any]) -> list[str]:
    """Comme `render`, mais destiné aux expressions qui produisent une liste."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_to_text(v) for v in value if _to_text(v)]

    if isinstance(value, str):
        match = _VAR_PATTERN.fullmatch(value.strip())
        if match:
            resolved = resolve(match.group(1), context)
            if isinstance(resolved, (list, tuple, set)):
                return [_to_text(v) for v in resolved if _to_text(v)]
            text = _to_text(resolved)
            return [text] if text else []
        text = render(value, context)
        return [text] if text else []

    return [_to_text(value)]


def resolve(expression: str, context: dict[str, Any]) -> Any:
    """
    Résout une expression du fichier de configuration.

    Formes admises :
      report.name              chemin pointé (attribut ou clé de dictionnaire)
      a + b                    concaténation (listes ou chaînes)
    """
    expression = expression.strip()

    if "+" in expression:
        parts = [resolve(p, context) for p in expression.split("+")]
        if any(isinstance(p, (list, tuple, set)) for p in parts):
            merged: list[Any] = []
            for part in parts:
                if isinstance(part, (list, tuple, set)):
                    merged.extend(sorted(part) if isinstance(part, set) else part)
                elif part not in (None, ""):
                    merged.append(part)
            return merged
        return "".join(_to_text(p) for p in parts)

    return _lookup(expression, context)


def _lookup(path: str, context: dict[str, Any]) -> Any:
    current: Any = context
    for part in path.split("."):
        part = part.strip()
        if not part:
            return None
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            if not hasattr(current, part):
                return None
            current = getattr(current, part)
    return current


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, set):
        return ", ".join(sorted(str(v) for v in value))
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


# ─────────────────────────────────────────────────────────────
#  Conditions `when`
# ─────────────────────────────────────────────────────────────


def evaluate(condition: Any, context: dict[str, Any]) -> bool:
    """
    Évalue une condition `when`.

    Formes admises :
      inputs.pages_secondaires        vrai si la valeur est vraie
      !inputs.pages_secondaires       négation
      ref.kind == mesure              égalité (comparaison textuelle, insensible à la casse)
    """
    if condition is None:
        return True
    if isinstance(condition, bool):
        return condition

    expression = str(condition).strip()
    if not expression:
        return True

    if expression.startswith("!"):
        return not evaluate(expression[1:], context)

    for operator in ("!=", "=="):
        if operator in expression:
            left_expr, right_expr = expression.split(operator, 1)
            left = _to_text(resolve(left_expr, context)).strip().lower()
            right = right_expr.strip().strip("'\"").lower()
            return (left == right) if operator == "==" else (left != right)

    return _is_truthy(resolve(expression, context))


def _is_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "non", "no", "0")
    return bool(value)


# ─────────────────────────────────────────────────────────────
#  Utilitaires internes
# ─────────────────────────────────────────────────────────────


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
