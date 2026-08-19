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
from src.parsers.tmdl.reader import indent_of, opens_block

_HEADER = re.compile(
    r"^measure\s+(?:'((?:[^']|'')+)'|\"((?:[^\"]|\"\")+)\"|(\S+))\s*=\s*(.*)?$",
)

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

        block, consumed = _collect_block(lines, index)
        measure = _parse_block(block, table_name)
        if measure:
            measures.append(measure)
        index += consumed

    return measures


def _collect_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Collecte les lignes d'un bloc mesure jusqu'au prochain bloc de même niveau."""
    indent = indent_of(lines[start])
    block = [lines[start]]

    index = start + 1
    while index < len(lines):
        stripped = lines[index].lstrip()
        if stripped and indent_of(lines[index]) <= indent and opens_block(stripped):
            break
        block.append(lines[index])
        index += 1

    return block, index - start


def _parse_block(block: list[str], table_name: str) -> DaxMeasure | None:
    """Construit une DaxMeasure depuis les lignes d'un bloc `measure`."""
    name, inline_expression, opens_fence = _parse_header(block[0].strip())
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

    measure.expression = _clean_expression(expression)
    return measure


def _parse_header(first_line: str) -> tuple[str | None, str | None, bool]:
    """
    Parse la ligne `measure <nom> = <reste>`.

    Les apostrophes internes d'un nom quoté sont doublées en TMDL
    (`measure 'Chiffre d''affaires'`).

    Retourne (nom, expression inline ou None, ouverture d'un bloc ```).
    """
    match = _HEADER.match(first_line)
    if not match:
        return None, None, False

    quoted_single, quoted_double, bare, rest = match.groups()
    if quoted_single is not None:
        name = quoted_single.replace("''", "'").strip()
    elif quoted_double is not None:
        name = quoted_double.replace('""', '"').strip()
    else:
        name = (bare or "").strip()

    rest = (rest or "").strip()
    if rest.startswith("```"):
        return name, None, True  # le bloc s'ouvre sur la ligne du `measure`
    return name, rest or None, False


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


def _clean_expression(lines: list[str]) -> str:
    """Retire les lignes vides aux extrémités et l'indentation commune."""
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""

    indent = min(indent_of(line) for line in non_empty)
    return "\n".join(line[indent:] for line in lines).strip()
