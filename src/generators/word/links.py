"""
Signets et liens internes du document.

Deux mécanismes cohabitent :

  - le plan pose des signets (`bookmark:` sur un titre) et peut viser une cible
    précise (`hyperlink:` sur une colonne de tableau) ;
  - toute mention d'un nom de mesure dans un texte écrit devient un lien vers
    la définition de cette mesure (`rendering.links.auto`).

`LinkIndex` regroupe les deux : il connaît les signets posés, les cibles
atteignables, et tient le bilan affiché en fin de génération.
"""

import hashlib
import re
import unicodedata
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from src import console
from src.config import DocConfig, render, resolve
from src.generators.measure_links import MeasureLinker, collect_measures

# Mise en forme appliquée aux liens si le style de caractère est introuvable.
_FALLBACK_COLOR = "0563C1"

# Longueur maximale d'un nom de signet accepté par Word.
_BOOKMARK_MAX_LENGTH = 40


class LinkIndex:
    """Pose les signets, écrit les liens et vérifie qu'aucun ne pointe dans le vide."""

    def __init__(self, config: DocConfig, context: dict[str, Any], style_ids: dict[str, str]):
        self.options = config.rendering["links"]
        self.auto = self.options.get("auto") or {}
        self.enabled = bool(self.options.get("enabled", True))
        self._style_ids = style_ids

        self.linker = self._build_linker(context) if self.enabled else None
        self._targets = set(self.linker.targets.values()) if self.linker else set()

        self._bookmarks: set[str] = set()  # signets réellement écrits
        self._anchors: dict[str, int] = {}  # cibles visées par un lien
        self._next_id = 0

    # ── Cibles ────────────────────────────────────────────────────
    def bookmark_for(self, raw_name: str) -> str:
        """Nom de signet d'une cible (`measure:Chiffre d'affaires` → signet Word)."""
        prefix = self.options.get("bookmark_prefix") or ""
        return bookmark_name(prefix + (raw_name or ""))

    def is_reachable(self, bookmark: str) -> bool:
        """
        Un lien explicite n'est écrit que si sa cible est une mesure documentée.

        Sans ce contrôle, une mesure absente du modèle (visuel pointant vers un
        autre jeu de données, mesure supprimée...) produirait dans Word un lien
        « Le signet n'existe pas ». Quand la détection automatique est
        désactivée, le plan reste maître de ses cibles.
        """
        if not bookmark:
            return False
        if self.linker is None or not self.linker.has_targets():
            return True
        return bookmark in self._targets or bookmark in self._bookmarks

    def self_bookmark(self, context: dict[str, Any]) -> str | None:
        """Signet de la mesure en cours de documentation (pas d'auto-référence)."""
        if self.linker is None or not self.auto.get("skip_self", True):
            return None
        name = getattr(context.get("measure"), "name", None)
        return self.linker.targets.get(name) if name else None

    # ── Écriture ──────────────────────────────────────────────────
    def split(self, line: str, skip_bookmark: str | None) -> list[tuple[str, str | None]]:
        """Découpe une ligne en segments liés / non liés."""
        if self.linker is None or not self.linker.has_targets():
            return [(line, None)]
        return self.linker.split(line, skip_bookmark=skip_bookmark)

    def add_bookmark(self, paragraph, raw_name: str) -> None:
        name = self.bookmark_for(raw_name)
        if not name or name in self._bookmarks:
            return

        self._bookmarks.add(name)
        self._next_id += 1

        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), str(self._next_id))
        start.set(qn("w:name"), name)

        # `w:pPr` doit rester le premier enfant du paragraphe.
        properties = paragraph._p.find(qn("w:pPr"))
        if properties is not None:
            properties.addnext(start)
        else:
            paragraph._p.insert(0, start)

        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(self._next_id))
        paragraph._p.append(end)

    def add_hyperlink(self, paragraph, text: str, bookmark: str) -> None:
        if not bookmark:
            paragraph.add_run(text)
            return

        self._anchors[bookmark] = self._anchors.get(bookmark, 0) + 1

        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("w:anchor"), bookmark)

        run = OxmlElement("w:r")
        run.append(self._run_properties())

        node = OxmlElement("w:t")
        node.text = text
        node.set(qn("xml:space"), "preserve")
        run.append(node)

        hyperlink.append(run)
        paragraph._p.append(hyperlink)

    def _run_properties(self):
        """
        Mise en forme du lien. `w:rStyle` attend l'identifiant du style, pas son
        nom : dans un template français « Hyperlink » a pour identifiant
        « Lienhypertexte ». Si le style est absent, la mise en forme est
        appliquée directement pour que le lien reste visible.
        """
        properties = OxmlElement("w:rPr")
        style_id = self._style_ids.get(self.options.get("style", "Hyperlink"))

        if style_id:
            style = OxmlElement("w:rStyle")
            style.set(qn("w:val"), style_id)
            properties.append(style)
            return properties

        color = OxmlElement("w:color")
        color.set(qn("w:val"), _FALLBACK_COLOR)
        underline = OxmlElement("w:u")
        underline.set(qn("w:val"), "single")
        properties.append(color)
        properties.append(underline)
        return properties

    # ── Bilan ─────────────────────────────────────────────────────
    def report(self) -> None:
        """Bilan des liens internes, affiché en fin de génération."""
        if self.linker is None:
            console.info("Liens internes désactivés")
            return

        measures = len(self._bookmarks & self._targets)
        console.info(
            f"Liens internes : {sum(self._anchors.values())} — {measures} mesures et "
            f"{len(self._bookmarks) - measures} autres emplacements atteignables"
        )

        dangling = sorted(set(self._anchors) - self._bookmarks)
        if dangling:
            console.warn(
                f"{len(dangling)} lien(s) sans signet correspondant : {', '.join(dangling[:5])}"
            )

        if self.linker.unlinked:
            names = sorted(self.linker.unlinked)
            console.warn(
                f"{len(names)} mesure(s) mentionnée(s) mais non documentée(s) "
                f"(hors périmètre `data.measures`) : {', '.join(names[:5])}"
            )

    # ── Construction ──────────────────────────────────────────────
    def _build_linker(self, context: dict[str, Any]) -> MeasureLinker | None:
        """
        Construit le répertoire « nom de mesure -> signet » à partir des mesures
        effectivement documentées dans le document.
        """
        if not self.auto.get("enabled", True):
            return None

        source = self.auto.get("source") or "model.tables_with_measures"
        target = self.auto.get("target") or "measure:{{ measure.name }}"
        excluded = {str(name) for name in self.auto.get("exclude") or []}

        targets: dict[str, str] = {}
        for measure in collect_measures(resolve(str(source).strip("{} "), context)):
            name = getattr(measure, "name", "")
            bookmark = self.bookmark_for(render(target, {**context, "measure": measure}))
            if name and bookmark and name not in excluded:
                targets[name] = bookmark

        report = context.get("report")
        known = [
            name for name in (getattr(report, "all_measures", {}) or {}) if name not in excluded
        ]

        return MeasureLinker(
            targets=targets,
            known_names=known,
            case_sensitive=bool(self.auto.get("case_sensitive", False)),
            min_length=int(self.auto.get("min_length", 2)),
            first_occurrence_only=bool(self.auto.get("first_occurrence_only", False)),
        )


def bookmark_name(name: str) -> str:
    """
    Nom de signet valide pour Word : lettres non accentuées, chiffres et
    underscores, 40 caractères maximum, ne commençant pas par un chiffre.

    Dès que le nettoyage perd de l'information (accents, espaces, ponctuation,
    longueur), une empreinte du nom d'origine est ajoutée : sans elle
    « Marge » et « Marge % » produiraient le même signet et les deux mesures
    partageraient la même cible.

    La fonction reste purement déterministe : la pose du signet et la
    résolution des liens qui le visent aboutissent au même nom.
    """
    raw = name or ""
    ascii_name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"\W+", "_", ascii_name).strip("_") or "signet"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"

    if cleaned == raw and len(cleaned) <= _BOOKMARK_MAX_LENGTH:
        return cleaned

    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
    return f"{cleaned[: _BOOKMARK_MAX_LENGTH - len(digest) - 1]}_{digest}"
