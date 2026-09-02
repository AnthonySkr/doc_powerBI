"""
Lecture du rapport Power BI au format PBIR.

    Report/definition/pages/<hash>/page.json
                                   visuals/<hash>/visual.json

Un `visual.json` décrit soit un visuel, soit un groupe (`visualGroup`) dont les
membres le désignent par `parentGroupName`.
"""

import os

from src import console
from src.models.data_models import PowerBIReport
from src.parsers.report.fields import parse_filters
from src.parsers.report.pages import load_page_order, parse_page, read_json

# Filtres posés sur le rapport entier. Le fichier a changé de place selon les
# versions du format PBIR : les deux emplacements sont essayés.
_REPORT_FILES = (os.path.join("definition", "report.json"), "report.json")

__all__ = ["parse_report"]


def parse_report(report_dir: str, report_name: str = "Rapport Power BI") -> PowerBIReport:
    """Parse le dossier `.Report/` d'un projet .pbip."""
    report = PowerBIReport(name=report_name)
    report.filters = _report_filters(report_dir)

    pages_dir = os.path.join(report_dir, "definition", "pages")
    if not os.path.isdir(pages_dir):
        console.warn(f"Dossier pages introuvable : '{pages_dir}'")
        return report

    page_order = load_page_order(pages_dir)

    for folder_name in sorted(os.listdir(pages_dir)):
        folder_path = os.path.join(pages_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        page = parse_page(folder_path, folder_name, page_order)
        if page:
            report.pages.append(page)

    report.pages.sort(key=lambda page: page.order)

    visuals = sum(len(page.visuals) for page in report.pages)
    groups = sum(len(page.groups) for page in report.pages)
    with_measures = sum(1 for page in report.pages for v in page.visuals if v.has_measures)
    console.info(
        f"{len(report.pages)} pages | {visuals} visuels ({with_measures} avec mesures) "
        f"| {groups} groupes"
    )
    return report


def _report_filters(report_dir: str) -> list:
    """
    Filtres posés sur le rapport entier (volet « Filtres sur toutes les pages »).

    Ils ne sont pas documentés page par page, mais une mesure qui n'apparaît
    que là est bel et bien employée par le rapport.
    """
    for relative in _REPORT_FILES:
        data = read_json(os.path.join(report_dir, relative))
        if data is not None:
            return parse_filters((data.get("filterConfig") or {}).get("filters", []))
    return []
