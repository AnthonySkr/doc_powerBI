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

from models.data_models import DaxMeasure, ModelTable

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


def load_all_tables_from_model(semantic_model_path: str) -> list[ModelTable]:
    """
    Charge les tables du modèle sémantique avec leur source et leurs étapes
    de transformation Power Query (partie « Table de données » de la doc).

    Args:
        semantic_model_path: Chemin vers le dossier .SemanticModel/

    Returns:
        Liste de ModelTable
    """
    tables: list[ModelTable] = []

    tables_dir = os.path.join(semantic_model_path, "definition", "tables")
    if not os.path.isdir(tables_dir):
        return tables

    for file_name in sorted(os.listdir(tables_dir)):
        if not file_name.endswith(".tmdl"):
            continue
        content = _read_file(os.path.join(tables_dir, file_name))
        if content is None:
            continue
        tables.append(_parse_table(content))

    print(f"  {len(tables)} tables chargées")
    return tables


def _parse_table(content: str) -> ModelTable:
    """Construit un ModelTable depuis le contenu d'un fichier .tmdl."""
    name = _extract_table_name(content)
    m_code = _extract_partition_source(content)
    steps = _parse_m_steps(m_code)

    return ModelTable(
        name=name,
        source=_extract_source_expression(steps, m_code),
        transformation_steps=steps,
        is_hidden=_is_table_hidden(content),
    )


def _is_table_hidden(content: str) -> bool:
    """Détecte `isHidden` au niveau de la table (avant le premier sous-bloc)."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first_token = stripped.split()[0].lower().rstrip(":")
        if first_token in _BLOCK_KEYWORDS and first_token != "table":
            return False
        if stripped.lower() == "ishidden":
            return True
    return False


def _extract_partition_source(content: str) -> str:
    """Extrait le code M du bloc `partition ... source = ...`."""
    lines = content.splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not re.match(r"^source\s*=", stripped):
            continue

        inline = stripped.split("=", 1)[1].strip()
        if inline and inline != "```":
            return inline

        # Expression multi-lignes : on collecte tant que l'indentation
        # reste supérieure à celle de la ligne `source =`.
        indent = len(line) - len(line.lstrip())
        collected: list[str] = []
        for next_line in lines[i + 1 :]:
            if not next_line.strip():
                collected.append("")
                continue
            if next_line.strip() == "```":
                break
            if (len(next_line) - len(next_line.lstrip())) <= indent:
                break
            collected.append(next_line)
        return "\n".join(collected).strip()

    return ""


def _parse_m_steps(m_code: str) -> list[dict[str, str]]:
    """
    Découpe un script Power Query `let ... in ...` en étapes.

    Returns:
        Liste de {"name": nom de l'étape, "expression": expression associée}
    """
    if not m_code:
        return []

    body = _let_body(m_code)
    if body is None:
        return []

    steps: list[dict[str, str]] = []
    for chunk in _split_top_level(body, ","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, expression = _split_first_top_level(chunk, "=")
        if not name:
            continue
        steps.append(
            {
                "name": _clean_m_identifier(name),
                "expression": " ".join(expression.split()),
            }
        )
    return steps


def _let_body(m_code: str) -> str | None:
    """Isole le corps entre `let` et le `in` final (hors chaînes/parenthèses)."""
    match = re.search(r"\blet\b", m_code)
    if not match:
        return None

    body = m_code[match.end() :]
    last_in = None
    for token in re.finditer(r"\bin\b", body):
        if _depth_at(body, token.start()) == 0:
            last_in = token.start()

    return body[:last_in] if last_in is not None else body


def _depth_at(text: str, index: int) -> int:
    """Profondeur de parenthésage à une position, en ignorant les chaînes."""
    depth = 0
    in_string = False
    i = 0
    while i < index and i < len(text):
        char = text[i]
        if char == '"':
            in_string = not in_string
        elif not in_string:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
        i += 1
    return depth


def _split_top_level(text: str, separator: str) -> list[str]:
    """Découpe une chaîne sur un séparateur situé au niveau 0."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False

    for char in text:
        if char == '"':
            in_string = not in_string
        elif not in_string:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == separator and depth == 0:
                parts.append("".join(current))
                current = []
                continue
        current.append(char)

    parts.append("".join(current))
    return parts


def _split_first_top_level(text: str, separator: str) -> tuple[str, bool, str]:
    """Sépare `text` au premier séparateur de niveau 0."""
    parts = _split_top_level(text, separator)
    if len(parts) < 2:
        return "", False, text
    return parts[0].strip(), True, separator.join(parts[1:]).strip()


def _clean_m_identifier(name: str) -> str:
    """Nettoie un identifiant Power Query : #"Lignes filtrées" → Lignes filtrées"""
    name = name.strip()
    if name.startswith('#"') and name.endswith('"'):
        return name[2:-1]
    return name.strip('"')


def _extract_source_expression(steps: list[dict[str, str]], m_code: str) -> str:
    """Détermine la source de la table (paramètres de connexion)."""
    for step in steps:
        if step["name"].lower() in ("source", "src"):
            return step["expression"]
    if steps:
        return steps[0]["expression"]
    return " ".join(m_code.split())[:500]


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
    name, inline_expr, opens_fence = _parse_header(first_line)
    if not name:
        return None

    display_folder = "Racine"
    description = ""
    format_string = ""
    is_hidden = False
    expression_lines: list[str] = []

    mode = "expression"
    in_backtick = opens_fence

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


def _parse_header(first_line: str) -> tuple[str | None, str | None, bool]:
    """
    Parse : measure NomOuQuote = [expression]

    Les apostrophes internes d'un nom quoté sont doublées en TMDL
    (measure 'Chiffre d''affaires').

    Retourne (nom, expression_inline_ou_None, ouverture_bloc_backticks).
    """
    pattern = re.match(
        r"^measure\s+(?:'((?:[^']|'')+)'|\"((?:[^\"]|\"\")+)\"|(\S+))\s*=\s*(.*)?$",
        first_line.strip(),
    )
    if not pattern:
        return None, None, False

    quoted_single, quoted_double, bare = pattern.group(1), pattern.group(2), pattern.group(3)
    if quoted_single is not None:
        name = quoted_single.replace("''", "'").strip()
    elif quoted_double is not None:
        name = quoted_double.replace('""', '"').strip()
    else:
        name = (bare or "").strip()

    rest = (pattern.group(4) or "").strip()

    if rest.startswith("```"):
        # Le bloc d'expression s'ouvre sur la ligne du `measure`.
        return name, None, True

    if not rest:
        return name, None, False

    return name, rest, False


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
