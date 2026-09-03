"""
Lecture du modèle sémantique (dossier `.SemanticModel/definition/tables/`).

    measures, tables = load_semantic_model(path)

Chaque fichier .tmdl décrit une table : il est lu une seule fois, et fournit
à la fois la table (source, étapes Power Query) et ses mesures DAX.
"""

from src import console
from src.models.data_models import DaxMeasure, ModelTable
from src.parsers.tmdl.measures import extract_measures
from src.parsers.tmdl.reader import read_file, table_name, tmdl_files
from src.parsers.tmdl.tables import parse_table

__all__ = ["load_semantic_model"]


def load_semantic_model(
    semantic_model_path: str,
) -> tuple[dict[str, DaxMeasure], list[ModelTable]]:
    """
    Charge les tables et les mesures du modèle sémantique.

    Les noms de mesures sont uniques dans un modèle Power BI : un doublon
    signale une anomalie, et la seconde définition est ignorée.
    """
    paths = tmdl_files(semantic_model_path)
    console.done(f"{len(paths)} fichier(s) de table lu(s)")

    measures: dict[str, DaxMeasure] = {}
    tables: list[ModelTable] = []

    for path in paths:
        content = read_file(path)
        if content is None:
            continue

        tables.append(parse_table(content))
        for measure in extract_measures(content, table_name(content)):
            existing = measures.get(measure.name)
            if existing is not None:
                console.detail(
                    f"Doublon ignoré : '{measure.name}' "
                    f"(table '{measure.table_name}' vs '{existing.table_name}')"
                )
                continue
            measures[measure.name] = measure

    console.done(f"{len(tables)} table(s) et {len(measures)} mesure(s) chargée(s)")
    return measures, tables
