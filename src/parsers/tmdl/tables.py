"""
Extraction d'une table du modèle sémantique depuis son fichier .tmdl :
nom, visibilité, colonnes calculées, et code Power Query de sa partition.
"""

import re

from src.models.data_models import ModelTable
from src.parsers.tmdl import powerquery
from src.parsers.tmdl.columns import extract_calculated_columns
from src.parsers.tmdl.reader import indent_of, opens_block, table_name


def parse_table(content: str) -> ModelTable:
    """Construit un ModelTable depuis le contenu d'un fichier .tmdl."""
    m_code = _partition_source(content)
    steps = powerquery.parse_steps(m_code)

    return ModelTable(
        name=table_name(content),
        source=powerquery.source_expression(steps, m_code),
        transformation_steps=steps,
        calculated_columns=extract_calculated_columns(content),
        is_hidden=_is_hidden(content),
    )


def _is_hidden(content: str) -> bool:
    """Détecte `isHidden` au niveau de la table (avant le premier sous-bloc)."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower() == "ishidden":
            return True
        if opens_block(stripped) and not stripped.lower().startswith("table"):
            return False
    return False


def _partition_source(content: str) -> str:
    """Extrait le code M du bloc `partition ... source = ...`."""
    lines = content.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not re.match(r"^source\s*=", stripped):
            continue

        inline = stripped.split("=", 1)[1].strip()
        if inline and inline != "```":
            return inline

        # Expression multi-lignes : on collecte tant que l'indentation reste
        # supérieure à celle de la ligne `source =`.
        indent = indent_of(line)
        collected: list[str] = []
        for next_line in lines[index + 1 :]:
            if not next_line.strip():
                collected.append("")
            elif next_line.strip() == "```" or indent_of(next_line) <= indent:
                break
            else:
                collected.append(next_line)
        return "\n".join(collected).strip()

    return ""
