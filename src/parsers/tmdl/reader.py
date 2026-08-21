"""
Lecture des fichiers .tmdl : encodage, nom de table, découpage en blocs.

Mesures et colonnes calculées s'écrivent de la même façon — un mot-clé, un nom,
un `=` puis une expression DAX — et partagent donc ici leur découpage.
"""

import os
import re

from src import console

# Mots-clés ouvrant un bloc TMDL. Ils servent de bornes : un bloc `measure`
# s'arrête au prochain mot-clé de même niveau d'indentation.
BLOCK_KEYWORDS = frozenset(
    {
        "column",
        "partition",
        "hierarchy",
        "annotation",
        "measure",
        "table",
        "relationship",
        "role",
    }
)

_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")

# `<mot-clé> 'Nom quoté'|"Nom"|Nom = <reste de la ligne>`
_HEADER = r"^{keyword}\s+(?:'((?:[^']|'')+)'|\"((?:[^\"]|\"\")+)\"|(\S+))\s*=\s*(.*)?$"

# Propriété TMDL : `dataType: int64`, ou un simple drapeau `isHidden`.
_PROPERTY_LINE = re.compile(r"^\w+\s*:")
_FLAG_LINE = re.compile(r"^is[A-Z]\w*$")


def tmdl_files(semantic_model_path: str) -> list[str]:
    """Chemins des fichiers .tmdl de `definition/tables/`, triés."""
    tables_dir = os.path.join(semantic_model_path, "definition", "tables")
    if not os.path.isdir(tables_dir):
        console.warn(f"Dossier tables introuvable : '{tables_dir}'")
        return []

    return sorted(
        os.path.join(tables_dir, name) for name in os.listdir(tables_dir) if name.endswith(".tmdl")
    )


def read_file(path: str) -> str | None:
    """Lit un fichier en testant plusieurs encodages."""
    for encoding in _ENCODINGS:
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    console.warn(f"Impossible de lire '{path}'")
    return None


def table_name(content: str) -> str:
    """Extrait le nom de la table : `table 'Nom'` ou `table Nom`."""
    match = re.search(r"^table\s+'([^']+)'|^table\s+(\S+)", content, re.MULTILINE)
    return (match.group(1) or match.group(2)) if match else "Table inconnue"


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def opens_block(stripped_line: str) -> bool:
    """Vrai si la ligne commence un bloc TMDL (`measure ...`, `column ...`)."""
    if not stripped_line:
        return False
    return stripped_line.split()[0].lower().rstrip(":") in BLOCK_KEYWORDS


# ─────────────────────────────────────────────────────────────
#  Blocs `<mot-clé> <nom> = <expression>`
# ─────────────────────────────────────────────────────────────


def collect_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Collecte les lignes d'un bloc jusqu'au prochain bloc de même niveau."""
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


def block_header(first_line: str, keyword: str) -> tuple[str | None, str | None, bool]:
    """
    Parse la ligne d'ouverture `<mot-clé> <nom> = <reste>`.

    Les apostrophes internes d'un nom quoté sont doublées en TMDL
    (`measure 'Chiffre d''affaires'`).

    Retourne (nom, expression inline ou None, ouverture d'un bloc ```).
    """
    match = re.match(_HEADER.format(keyword=keyword), first_line)
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
        return name, None, True  # le bloc s'ouvre sur la ligne du mot-clé
    return name, rest or None, False


def is_property(stripped_line: str) -> bool:
    """
    Vrai si la ligne est une propriété TMDL (`dataType: int64`, `isHidden`).

    C'est ce qui marque la fin d'une expression écrite sans délimiteurs.
    """
    return bool(_PROPERTY_LINE.match(stripped_line) or _FLAG_LINE.match(stripped_line))


def dedent_expression(lines: list[str]) -> str:
    """Retire les lignes vides aux extrémités et l'indentation commune."""
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""

    indent = min(indent_of(line) for line in non_empty)
    return "\n".join(line[indent:] for line in lines).strip()
