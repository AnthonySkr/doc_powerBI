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
from src.parsers.report.pages import load_page_order, parse_page

__all__ = ["parse_report"]


def parse_report(report_dir: str, report_name: str = "Rapport Power BI") -> PowerBIReport:
    """Parse le dossier `.Report/` d'un projet .pbip."""
    report = PowerBIReport(name=report_name)

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
