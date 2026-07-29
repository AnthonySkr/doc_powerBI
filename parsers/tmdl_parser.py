"""
Parseur de fichiers .tmdl pour extraire les mesures DAX.
Gère :
  - Noms de tables/mesures avec espaces entre quotes
  - Expressions multi-lignes avec délimiteurs ```
  - Expressions inline (sur la même ligne que le nom)
  - Blocs column/partition ignorés
"""

import os
import re

from models.data_models import DaxMeasure

_BLOCK_KEYWORDS = frozenset(
    [
        "column",
        "partition",
        "hierarchy",
        "annotation",
        "measure",
        "table",
        "relationship",
        "role",
    ]
)


def load_all_measures_from_model(semantic_model_path: str) -> dict[str, DaxMeasure]:
    """
    Charge toutes les mesures DAX depuis le dossier du modèle sémantique.

    Args:
        semantic_model_path: Chemin vers le dossier .SemanticModel/

    Returns:
        Dictionnaire {nom_mesure: DaxMeasure}
    """
    all_measures: dict[str, DaxMeasure] = {}

    tables_dir = os.path.join(semantic_model_path, "definition", "tables")
    if not os.path.isdir(tables_dir):
        print(f"  Dossier tables introuvable : '{tables_dir}'")
        return all_measures

    tmdl_files = [
        os.path.join(tables_dir, f) for f in os.listdir(tables_dir) if f.endswith(".tmdl")
    ]
    print(f"  Fichiers .tmdl trouvés : {len(tmdl_files)}")

    for path in sorted(tmdl_files):
        measures = _parse_tmdl_file(path)
        for m in measures:
            if m.name in all_measures:
                print(
                    f"    Doublon ignoré : '{m.name}' "
                    f"(table '{m.table_name}' vs '{all_measures[m.name].table_name}')"
                )
                continue
            all_measures[m.name] = m

    print(f"  {len(all_measures)} mesures chargées")
    return all_measures


# ─────────────────────────────────────────────────────────────
#  Lecture du fichier
# ─────────────────────────────────────────────────────────────


def _parse_tmdl_file(file_path: str) -> list[DaxMeasure]:
    """Parse un fichier .tmdl et retourne les mesures qu'il contient."""
    content = _read_file(file_path)
    if content is None:
        return []

    table_name = _extract_table_name(content)
    return _extract_measures(content, table_name)


def _read_file(path: str) -> str | None:
    """Lit un fichier en testant plusieurs encodages."""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError, LookupError:
            continue
    print(f"  Impossible de lire '{path}'")
    return None


def _extract_table_name(content: str) -> str:
    """Extrait le nom de la table : table 'Nom' ou table Nom"""
    match = re.search(r"^table\s+'([^']+)'|^table\s+(\S+)", content, re.MULTILINE)
    if match:
        return match.group(1) or match.group(2)
    return "Table inconnue"


# ─────────────────────────────────────────────────────────────
#  Extraction des mesures
# ─────────────────────────────────────────────────────────────


def _extract_measures(content: str, table_name: str) -> list[DaxMeasure]:
    """Repère chaque bloc 'measure ...' et le parse."""
    lines = content.splitlines()
    measures = []
    i = 0

    while i < len(lines):
        stripped = lines[i].lstrip()
        if re.match(r"^measure\s+", stripped):
            indent = len(lines[i]) - len(stripped)
            block, consumed = _collect_block(lines, i, indent)
            measure = _parse_block(block, table_name)
            if measure:
                measures.append(measure)
            i += consumed
        else:
            i += 1

    return measures


def _collect_block(lines: list[str], start: int, indent: int) -> tuple[list[str], int]:
    """Collecte les lignes d'un bloc mesure jusqu'au prochain bloc de même niveau."""
    block = [lines[start]]
    i = start + 1

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        if not stripped:
            block.append(line)
            i += 1
            continue

        current_indent = len(line) - len(stripped)
        if current_indent <= indent:
            first_token = stripped.split()[0].lower().rstrip(":")
            if first_token in _BLOCK_KEYWORDS:
                break

        block.append(line)
        i += 1

    return block, i - start


def _parse_block(block_lines: list[str], table_name: str) -> DaxMeasure | None:
    """Parse un bloc de lignes en DaxMeasure."""
    if not block_lines:
        return None

    first_line = block_lines[0].strip()
    name, inline_expr = _parse_header(first_line)
    if not name:
        return None

    display_folder = "Racine"
    description = ""
    format_string = ""
    is_hidden = False
    expression_lines: list[str] = []

    mode = "expression"
    in_backtick = False

    if inline_expr is not None:
        expression_lines.append(inline_expr)
        mode = "properties"

    for line in block_lines[1:]:
        stripped = line.strip()

        # ── Gestion des blocs ``` ──
        if not in_backtick and (stripped == "```" or stripped.startswith("```")):
            in_backtick = True
            continue

        if in_backtick:
            if stripped == "```" or stripped.endswith("```"):
                in_backtick = False
                mode = "properties"
                continue
            expression_lines.append(line)
            continue

        # ── Hors backtick ──
        if mode == "expression":
            prop = _detect_property(stripped)
            if prop:
                mode = "properties"
                display_folder, description, format_string, is_hidden = _apply_property(
                    prop,
                    stripped,
                    display_folder,
                    description,
                    format_string,
                    is_hidden,
                )
            else:
                expression_lines.append(line)
        else:
            prop = _detect_property(stripped)
            if prop:
                display_folder, description, format_string, is_hidden = _apply_property(
                    prop,
                    stripped,
                    display_folder,
                    description,
                    format_string,
                    is_hidden,
                )

    expression = _clean_expression(expression_lines)

    return DaxMeasure(
        name=name,
        expression=expression,
        table_name=table_name,
        display_folder=display_folder,
        description=description,
        format_string=format_string,
        is_hidden=is_hidden,
    )


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────


def _parse_header(first_line: str) -> tuple[str | None, str | None]:
    """
    Parse : measure NomOuQuote = [expression]
    Retourne (nom, expression_inline_ou_None).
    """
    pattern = re.match(
        r"^measure\s+(?:'([^']+)'|\"([^\"]+)\"|(\S+))\s*=\s*(.*)?$",
        first_line.strip(),
    )
    if not pattern:
        return None, None

    name = (pattern.group(1) or pattern.group(2) or pattern.group(3) or "").strip()
    rest = (pattern.group(4) or "").strip()

    if not rest or rest.startswith("```"):
        return name, None

    return name, rest


def _detect_property(stripped: str) -> str | None:
    """Détecte si une ligne est une propriété TMDL connue."""
    if not stripped:
        return None

    lower = stripped.lower()

    if lower == "ishidden":
        return "ishidden"

    match = re.match(r"^(\w+)\s*:", stripped)
    if match:
        key = match.group(1).lower()
        if key in (
            "formatstring",
            "displayfolder",
            "description",
            "lineagetag",
            "annotation",
        ):
            return key

    return None


def _apply_property(
    key: str,
    line: str,
    display_folder: str,
    description: str,
    format_string: str,
    is_hidden: bool,
) -> tuple[str, str, str, bool]:
    """Applique une propriété et retourne les valeurs mises à jour."""
    k = key.lower()

    if k == "formatstring":
        match = re.search(r"formatString:\s*(.+)", line, re.IGNORECASE)
        if match:
            format_string = match.group(1).strip().strip("'\"")

    elif k == "displayfolder":
        match = re.search(r"displayFolder:\s*(.+)", line, re.IGNORECASE)
        if match:
            val = match.group(1).strip().strip("'\"")
            display_folder = val if val else "Racine"

    elif k == "description":
        match = re.search(r"description:\s*(.+)", line, re.IGNORECASE)
        if match:
            description = match.group(1).strip().strip("'\"")

    elif k == "ishidden":
        is_hidden = True

    return display_folder, description, format_string, is_hidden


def _clean_expression(lines: list[str]) -> str:
    """Nettoie l'expression DAX : supprime lignes vides aux extrémités, retire l'indentation commune."""
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return ""

    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return ""

    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
    cleaned = [l[min_indent:] if len(l) >= min_indent else l for l in lines]
    return "\n".join(cleaned).strip()
