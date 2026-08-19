"""
Conduite de la régénération incrémentale, côté écriture.

Le builder délègue ici trois questions :
  - quel élément suis-je en train d'écrire, et a-t-il changé ? (`enter_element`)
  - dois-je reprendre un texte du document précédent ? (`restore`)
  - comment le signaler visuellement ? (`highlight`)
"""

from contextlib import contextmanager
from typing import Any

from docx.enum.text import WD_COLOR_INDEX

from src.config import DocConfig, render
from src.merge import CHANGED, NEW, ChangeLog, PreviousDocument, markers

_HIGHLIGHTS = {
    "yellow": WD_COLOR_INDEX.YELLOW,
    "green": WD_COLOR_INDEX.BRIGHT_GREEN,
    "turquoise": WD_COLOR_INDEX.TURQUOISE,
    "gray": WD_COLOR_INDEX.GRAY_25,
    "none": None,
}


class MergeWriter:
    """Marqueurs, reprise des textes et surlignage, pour un document en cours d'écriture."""

    def __init__(self, doc, config: DocConfig, previous: PreviousDocument | None):
        self.doc = doc
        self.previous = previous or PreviousDocument()
        self.options = config.merge
        self.enabled = bool(self.options.get("enabled", True))

        self.log = ChangeLog(is_update=self.previous.exists)
        self._stack: list[tuple[str, str]] = []  # (identifiant, état) des éléments imbriqués

    # ── Élément documenté ─────────────────────────────────────────
    @contextmanager
    def element(self, section: dict[str, Any], context: dict[str, Any]):
        """
        Ouvre un élément documenté : pose son marqueur et retient son état.

        Un élément est une section du plan portant un `bookmark:` — c'est déjà
        son identifiant stable (`measure:Marge`, `visual:<page>:<visuel>`). Son
        `fingerprint:` décrit l'état technique dont dépend la documentation.
        """
        bookmark = section.get("bookmark")
        if not self.enabled or not bookmark:
            yield None
            return

        element_id = render(bookmark, context)
        digest = markers.fingerprint(render(section.get("fingerprint"), context))
        status = self.previous.status(element_id, digest)

        self.log.record(element_id, status)
        markers.write(self.doc, markers.element(element_id, digest))

        self._stack.append((element_id, status))
        try:
            yield status
        finally:
            self._stack.pop()

    @property
    def current_id(self) -> str:
        return self._stack[-1][0] if self._stack else ""

    @property
    def current_status(self) -> str:
        return self._stack[-1][1] if self._stack else ""

    # ── Zone rédigée par l'utilisateur ────────────────────────────
    def restore(self, block: dict[str, Any]) -> list[str]:
        """Texte saisi dans cette zone lors de la génération précédente, s'il existe."""
        key = self._slot_key(block)
        if not key or not self.options.get("keep_user_text", True):
            return []

        texts = self.previous.text_for(key)
        if texts:
            self.log.restored += 1
        return texts

    @contextmanager
    def slot(self, block: dict[str, Any]):
        """Encadre une zone rédigeable par ses marqueurs de début et de fin."""
        key = self._slot_key(block)
        if not key:
            yield
            return

        markers.write(self.doc, markers.slot(key))
        try:
            yield
        finally:
            markers.write(self.doc, markers.slot_end())

    def _slot_key(self, block: dict[str, Any]) -> str:
        block_id = block.get("id")
        if not self.enabled or not block_id:
            return ""
        return markers.slot_key(self.current_id, str(block_id))

    # ── Signalement visuel ────────────────────────────────────────
    def highlight_restored(self, paragraph) -> None:
        """
        Surligne un texte repris dont l'élément a changé techniquement : la
        rédaction porte peut-être sur une version périmée du visuel ou du DAX.
        """
        if self.current_status == CHANGED:
            self._apply(paragraph, self.options.get("highlight_changed", "yellow"))

    def highlight_new(self, paragraph) -> None:
        """Surligne la zone à rédiger d'un élément apparu depuis la dernière version."""
        if self.log.is_update and self.current_status == NEW:
            self._apply(paragraph, self.options.get("highlight_new", "none"))

    def _apply(self, paragraph, color_name: Any) -> None:
        color = _HIGHLIGHTS.get(str(color_name).lower())
        if color is None:
            return
        for run in paragraph.runs:
            run.font.highlight_color = color
