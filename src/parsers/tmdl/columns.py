"""
Extraction des colonnes calculées d'un fichier .tmdl.

Une colonne calculée est un bloc `column` porteur d'une expression DAX ; une
colonne ordinaire n'en a pas, elle se contente de pointer vers la source :

    column Marge = [Chiffre d'affaires] - [Coût]      colonne calculée
        dataType: double

    column Montant                                    colonne ordinaire
        sourceColumn: Montant
"""

from src.models.data_models import CalculatedColumn
from src.parsers.tmdl.reader import (
    block_header,
    collect_block,
    dedent_expression,
    is_property,
    opens_block,
)


def extract_calculated_columns(content: str) -> list[CalculatedColumn]:
    """Repère chaque bloc `column <nom> = ...` du fichier et le parse."""
    lines = content.splitlines()
    columns: list[CalculatedColumn] = []
    index = 0

    while index < len(lines):
        if not lines[index].lstrip().startswith("column "):
            index += 1
            continue

        block, consumed = collect_block(lines, index)
        column = _parse_block(block)
        if column:
            columns.append(column)
        index += consumed

    return columns


def _parse_block(block: list[str]) -> CalculatedColumn | None:
    """
    Construit une CalculatedColumn depuis les lignes d'un bloc `column`.

    Retourne None pour une colonne ordinaire : sans `=`, il n'y a pas
    d'expression, donc rien à documenter ici.
    """
    name, inline_expression, opens_fence = block_header(block[0].strip(), "column")
    if not name:
        return None

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

        if is_property(stripped) or opens_block(stripped):
            in_expression = False
        elif in_expression:
            expression.append(line)

    text = dedent_expression(expression)
    return CalculatedColumn(name=name, expression=text) if text else None
