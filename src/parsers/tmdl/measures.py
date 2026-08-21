"""
Extraction des mesures DAX d'un fichier .tmdl.

Un bloc mesure prend l'une de ces formes :

    measure 'Chiffre d''affaires' = SUM(Ventes[Montant])      expression inline
    measure Marge = ```                                       expression multi-lignes
            DIVIDE([Resultat], [Chiffre d'affaires])
            ```
        formatString: #,0
        displayFolder: Indicateurs
"""

import re

from src.models.data_models import DaxMeasure
from src.parsers.tmdl.reader import block_header, collect_block, dedent_expression

# Propriétés TMDL reprises dans DaxMeasure : clé TMDL -> attribut du modèle.
_PROPERTIES = {
    "formatstring": "format_string",
    "displayfolder": "display_folder",
    "description": "description",
}

# Propriétés reconnues mais volontairement ignorées : les rencontrer signale
# la fin de l'expression DAX.
_IGNORED_PROPERTIES = frozenset({"lineagetag", "annotation"})


def extract_measures(content: str, table_name: str) -> list[DaxMeasure]:
    """Repère chaque bloc `measure ...` du fichier et le parse."""
    lines = content.splitlines()
    measures: list[DaxMeasure] = []
    index = 0

    while index < len(lines):
        if not lines[index].lstrip().startswith("measure "):
            index += 1
            continue

        block, consumed = collect_block(lines, index)
        measure = _parse_block(block, table_name)
        if measure:
            measures.append(measure)
        index += consumed

    return measures


def _parse_block(block: list[str], table_name: str) -> DaxMeasure | None:
    """Construit une DaxMeasure depuis les lignes d'un bloc `measure`."""
    name, inline_expression, opens_fence = block_header(block[0].strip(), "measure")
    if not name:
        return None

    measure = DaxMeasure(name=name, expression="", table_name=table_name)
    expression: list[str] = []

    in_fence = opens_fence
    # Tant qu'aucune propriété n'a été rencontrée, les lignes libres font
    # partie de l'expression DAX.
    in_expression = inline_expression is None

    if inline_expression is not None:
        expression.append(inline_expression)

    for line in block[1:]:
        stripped = line.strip()

        if in_fence:
            if stripped == "```" or stripped.endswith("```"):
                in_fence = False
                in_expression = False
            else:
                expression.append(line)
            continue

        if stripped.startswith("```"):
            in_fence = True
            continue

        if _apply_property(measure, stripped):
            in_expression = False
        elif in_expression:
            expression.append(line)

    measure.expression = dedent_expression(expression)
    return measure


def _apply_property(measure: DaxMeasure, line: str) -> bool:
    """
    Applique une propriété TMDL à la mesure.

    Retourne True dès que la ligne *est* une propriété, même ignorée : c'est ce
    qui marque la fin de l'expression DAX.
    """
    if not line:
        return False

    if line.lower() == "ishidden":
        measure.is_hidden = True
        return True

    match = re.match(r"^(\w+)\s*:\s*(.*)$", line)
    if not match:
        return False

    key = match.group(1).lower()
    if key in _IGNORED_PROPERTIES:
        return True

    attribute = _PROPERTIES.get(key)
    if attribute is None:
        return False

    value = match.group(2).strip().strip("'\"")
    if value:
        setattr(measure, attribute, value)
    return True
