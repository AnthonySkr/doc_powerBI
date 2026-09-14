"""
L'extraction proprement dite : le `.pbip` lu, croisé, rassemblé.

Trois sources se rejoignent ici :

    le modèle sémantique   tables, mesures DAX, étapes Power Query
    les dépendances        ce dont chaque mesure a besoin, et qui l'emploie
    le rapport             pages, groupes, visuels, filtres

Le croisement est ce qui fait de ces trois lectures un seul objet : les mesures
que le rapport emploie réellement, dépendances comprises, sont relevées ici et
nulle part ailleurs.
"""

import os

from src.apps.extract import dependencies
from src.apps.extract.pbip import PbipProject
from src.apps.extract.report import parse_report
from src.apps.extract.tmdl import load_semantic_model
from src.shared import console
from src.shared.exchange import Exchange
from src.shared.models import PowerBIReport

__all__ = ["ExtractError", "collect", "open_project"]


class ExtractError(Exception):
    """Le projet `.pbip` est introuvable ou incomplet."""


def open_project(pbip_path: str) -> PbipProject:
    """Ouvre un projet `.pbip`, ou dit ce qui lui manque."""
    if not os.path.isfile(pbip_path):
        raise ExtractError(f"Fichier introuvable : '{pbip_path}'")

    project = PbipProject(pbip_path)
    missing = project.missing()
    if missing:
        raise ExtractError(missing)
    return project


def collect(project: PbipProject) -> Exchange:
    """Lit le projet et retourne ce qui passera à l'application suivante."""
    report = _read(project)
    return Exchange(
        report=report,
        source=project.path,
        produced_by="extract",
    )


def _read(project: PbipProject) -> PowerBIReport:
    """Lit le modèle sémantique et le rapport, puis croise les deux."""
    all_measures, tables = load_semantic_model(project.semantic_model_dir)  # type: ignore[arg-type]
    if all_measures:
        dependencies.analyze_dependencies(all_measures)
        console.done(f"dépendances calculées pour {len(all_measures)} mesure(s)")

    report = parse_report(project.report_dir, report_name=project.name)  # type: ignore[arg-type]
    report.all_measures = all_measures
    report.tables = tables
    report.measures_used_in_report = dependencies.measures_used_in_report(report, all_measures)

    console.done(f"{len(report.measures_in_visuals)} mesure(s) affichée(s) dans les visuels")
    console.done(
        f"{len(report.measures_used_in_report)} mesure(s) à documenter (dépendances comprises)"
    )
    return report
