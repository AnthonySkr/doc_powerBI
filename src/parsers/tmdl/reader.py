"""Lecture des fichiers .tmdl : encodage, nom de table, découpage en blocs."""

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
