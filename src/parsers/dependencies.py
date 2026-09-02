"""
Dépendances entre mesures DAX.

Une expression DAX référence d'autres mesures et des colonnes entre crochets :
`DIVIDE([Marge], [Chiffre d'affaires])`. Ce module en déduit, pour chaque
mesure, l'ensemble transitif des mesures et des colonnes dont elle dépend,
ainsi que la relation inverse (« qui m'utilise ? »).
"""

import re

from src.models.data_models import DaxMeasure, PowerBIReport

# 'Table'[Identifiant] ou [Identifiant]
_IDENTIFIER = re.compile(r"(?:'[^']+'\[([^\]]+)\])|\[([^\]]+)\]")


def analyze_dependencies(all_measures: dict[str, DaxMeasure]) -> None:
    """
    Calcule les dépendances de toutes les mesures et les renseigne en place :
    `dependent_measures`, `used_columns` et `used_by_measures`.
    """
    known = set(all_measures)

    direct_measures: dict[str, set[str]] = {}
    direct_columns: dict[str, set[str]] = {}
    for name, measure in all_measures.items():
        measures, columns = _identifiers(measure.expression, known)
        direct_measures[name] = measures
        direct_columns[name] = columns

    for name, measure in all_measures.items():
        reachable = _reachable(name, direct_measures)
        measure.dependent_measures = reachable - {name}
        measure.used_columns = set().union(*(direct_columns[n] for n in reachable))

    for name, measure in all_measures.items():
        measure.used_by_measures = {
            other for other, deps in direct_measures.items() if name in deps and other != name
        }


def measures_used_in_report(report: PowerBIReport, all_measures: dict[str, DaxMeasure]) -> set[str]:
    """
    Mesures employées par le rapport, plus leurs dépendances transitives.

    Employée veut dire affichée par un visuel — étiquettes de référence d'une
    carte comprises — ou posée en filtre, de rapport, de page ou de visuel.
    """
    used = report.measures_used
    dependencies = (all_measures[name].dependent_measures for name in used if name in all_measures)
    return used.union(*dependencies) if used else set()


def _identifiers(expression: str, known_measures: set[str]) -> tuple[set[str], set[str]]:
    """Sépare les identifiants d'une expression DAX en (mesures, colonnes)."""
    measures: set[str] = set()
    columns: set[str] = set()

    for match in _IDENTIFIER.finditer(expression or ""):
        identifier = match.group(1) or match.group(2)
        if not identifier:
            continue
        (measures if identifier in known_measures else columns).add(identifier)

    return measures, columns


def _reachable(start: str, direct: dict[str, set[str]]) -> set[str]:
    """Mesures atteignables depuis `start`, `start` compris (parcours en profondeur)."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(direct.get(name, ()))
    return seen
