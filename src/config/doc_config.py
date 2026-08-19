"""Chargement de `config_doc_pbi.yaml` et accès à ses différentes parties."""

import os
from typing import Any

import yaml

from src.config.defaults import DEFAULT_CONFIG_PATH, DEFAULTS


class DocConfig:
    """Accès typé aux différentes parties du fichier de configuration."""

    def __init__(self, raw: dict[str, Any] | None = None, path: str = DEFAULT_CONFIG_PATH):
        self.raw = _merge_defaults(raw or {}, DEFAULTS)
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
        section = self.find_section(section_id) or {}
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
