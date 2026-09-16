"""
L'extraction : le `.pbip` lu, croisé, rassemblé en `PowerBiMetadata`.

Trois sources se rejoignent ici :

    le modèle sémantique   tables, mesures DAX, étapes Power Query
    les dépendances        ce dont chaque mesure a besoin, et qui l'emploie
    le rapport             pages, groupes, visuels, filtres

Le croisement fait de ces trois lectures un seul objet : les mesures que le
rapport emploie réellement, dépendances comprises, sont relevées ici et nulle
part ailleurs.
"""

from pathlib import Path

from src.core import console
from src.core.models import PowerBiMetadata, PowerBIReport
from src.pbi_extractor import dependencies
from src.pbi_extractor.pbip import PbipProject
from src.pbi_extractor.report import parse_report
from src.pbi_extractor.tmdl import load_semantic_model


class ExtractError(Exception):
    """Le projet `.pbip` est introuvable ou incomplet."""


def open_project(pbip_path: str | Path) -> PbipProject:
    """Ouvre un projet `.pbip`, ou dit ce qui lui manque."""
    project = PbipProject.at(pbip_path)
    if not project.path.is_file():
        raise ExtractError(f"Fichier introuvable : '{project.path}'")

    missing = project.missing()
    if missing:
        raise ExtractError(missing)
    return project


def extract(project: PbipProject) -> PowerBiMetadata:
    """Lit le projet et retourne tout ce que la suite aura à savoir."""
    return PowerBiMetadata(report=_read(project), source=project.path)


def _read(project: PbipProject) -> PowerBIReport:
    """Lit le modèle sémantique et le rapport, puis croise les deux."""
    all_measures, tables = load_semantic_model(project.semantic_model_dir)
    if all_measures:
        dependencies.analyze_dependencies(all_measures)
        console.done(f"dépendances calculées pour {len(all_measures)} mesure(s)")

    report = parse_report(project.report_dir, report_name=project.name)
    report.all_measures = all_measures
    report.tables = tables
    report.measures_used_in_report = dependencies.measures_used_in_report(report, all_measures)

    console.done(f"{len(report.measures_in_visuals)} mesure(s) affichée(s) dans les visuels")
    console.done(
        f"{len(report.measures_used_in_report)} mesure(s) à documenter (dépendances comprises)"
    )
    return report
