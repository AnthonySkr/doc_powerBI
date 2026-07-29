"""Analyse des dépendances transitives entre mesures DAX."""

import re

from models.data_models import DaxMeasure


def extract_dax_identifiers(
    expression: str, all_measure_names: set[str]
) -> tuple[set[str], set[str]]:
    """
    Extrait les identifiants référencés dans une expression DAX.

    Returns:
        (mesures_trouvées, colonnes_trouvées)
    """
    found_measures = set()
    found_columns = set()

    if not expression:
        return found_measures, found_columns

    pattern = re.compile(r"(?:'[^']+'\[([^\]]+)\])|\[([^\]]+)\]")

    for match in pattern.finditer(expression):
        identifier = match.group(1) or match.group(2)
        if identifier:
            if identifier in all_measure_names:
                found_measures.add(identifier)
            else:
                found_columns.add(identifier)

    return found_measures, found_columns


def analyze_all_dependencies(all_measures: dict[str, DaxMeasure]) -> None:
    """
    Calcule les dépendances transitives de toutes les mesures (DFS).
    Modifie les objets DaxMeasure en place.
    """
    all_names = set(all_measures.keys())

    direct_deps: dict[str, set[str]] = {}
    direct_cols: dict[str, set[str]] = {}

    for name, measure in all_measures.items():
        measures_found, columns_found = extract_dax_identifiers(measure.expression, all_names)
        direct_deps[name] = measures_found
        direct_cols[name] = columns_found

    for name in all_measures:
        visited: set[str] = set()
        all_columns: set[str] = set()

        def dfs(current: str) -> None:
            if current in visited:
                return
            visited.add(current)
            all_columns.update(direct_cols.get(current, set()))
            for dep in direct_deps.get(current, set()):
                dfs(dep)

        dfs(name)

        all_measures[name].dependent_measures = visited
        all_measures[name].used_columns = all_columns


def get_measures_used_in_report(report, all_measures: dict[str, DaxMeasure]) -> set[str]:
    """
    Identifie toutes les mesures utilisées dans le rapport
    (directement + dépendances transitives).
    """
    directly_used: set[str] = set()
    for page in report.pages:
        for visual in page.visuals:
            for element in visual.elements:
                if element.type_category == "Mesure":
                    # Utiliser le Property (nom court de la mesure)
                    # display_name peut être un alias, on cherche aussi query_ref
                    parts = element.query_ref.split(".")
                    measure_name = parts[-1] if parts else element.display_name
                    directly_used.add(measure_name)

    all_used: set[str] = set()
    for name in directly_used:
        if name in all_measures:
            all_used.update(all_measures[name].dependent_measures)
        else:
            all_used.add(name)

    return all_used
