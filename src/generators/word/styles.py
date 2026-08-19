"""
Résolution des styles : clé de configuration → style existant du template.

Le plan désigne les styles par une clé (`code`, `ref_value`) ou par un
`{{ styles.x }}`. Si le style nommé est absent du template, le générateur
bascule sur `styles.fallback` et le signale une seule fois.
"""

from typing import Any

from docx.enum.style import WD_STYLE_TYPE

from src import console
from src.config import DocConfig, render


class StyleResolver:
    def __init__(self, doc, config: DocConfig, context: dict[str, Any]):
        self.config = config
        self.context = context

        self._available = {style.name for style in doc.styles}
        self._characters = {s.name for s in doc.styles if s.type == WD_STYLE_TYPE.CHARACTER}
        self.ids = {style.name: style.style_id for style in doc.styles}
        self._reported: set[str] = set()

    def paragraph(self, key: str | None) -> str:
        """Style de paragraphe existant, ou style de repli."""
        name = self.name(key or "normal")
        if name in self._available:
            return name

        fallback = self.config.styles.get("fallback", "Normal")
        if name and name != fallback:
            self._report(name, f"Style '{name}' absent du template — remplacé par '{fallback}'")
        return fallback if fallback in self._available else "Normal"

    def character(self, key: str | None) -> str | None:
        """Style de caractère existant, ou None (un style de paragraphe ne convient pas)."""
        name = self.name(key)
        if name in self._characters:
            return name
        if name:
            self._report(name, f"Style de caractère '{name}' absent du template — ignoré")
        return None

    def table(self, style_name: str) -> str | None:
        """Style de tableau existant, ou None."""
        if not style_name:
            return None
        if style_name in self._available:
            return style_name
        self._report(style_name, f"Style de tableau '{style_name}' absent du template — ignoré")
        return None

    def name(self, key: str | None) -> str:
        """Nom du style Word correspondant à une clé de configuration."""
        if not key:
            return ""
        key = str(key)
        return render(key, self.context) if "{{" in key else self.config.styles.get(key, key)

    def _report(self, name: str, message: str) -> None:
        if name not in self._reported:
            self._reported.add(name)
            console.warn(message)
