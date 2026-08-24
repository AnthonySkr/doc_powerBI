"""
Ce qui a été écrit *dans* les cellules d'un tableau du script.

Un tableau produit par le script est à lui : il le réécrit à chaque génération,
lignes et valeurs comprises. Mais on annote volontiers un tableau de l'intérieur
— une précision sous le libellé d'une ligne, une remarque dans la colonne d'à
côté. Le tableau étant réécrit d'un bloc, ces ajouts disparaissaient de leur
cellule (ils partent en annexe, voir `merge.orphans`).

Ce module les y ramène, sous une règle sans ambiguïté :

    la première ligne d'une cellule appartient au script — c'est sa donnée
    ce qui a été ajouté **en dessous**, dans la même cellule, est à vous

Une ligne du tableau est reconnue par les données du script qu'elle porte : si
elles n'ont pas bougé, c'est la même ligne, et ses annotations la retrouvent. Si
la ligne a changé ou disparu, l'annotation ne peut plus être rattachée à rien de
sûr : elle part en annexe plutôt que d'être posée sur une donnée qui n'est plus
celle qu'elle commentait.

Retoucher la donnée du script elle-même — écrire à la suite de son texte, dans
sa ligne à lui — reste une réécriture : le script la reprend, et la version
retouchée part en annexe.
"""

from docx.oxml.ns import qn

from src.merge import markers

_TABLE = qn("w:tbl")
_ROW = qn("w:tr")
_CELL = qn("w:tc")
_PARAGRAPH = qn("w:p")


def reconcile(old_table, fresh_table, copy) -> bool:
    """
    Reporte dans le tableau neuf les contenus ajoutés dans ses cellules.

    Tout ou rien : les cellules d'accueil sont d'abord toutes résolues, et rien
    n'est écrit si l'une d'elles manque. Sans cela un tableau à moitié
    rapproché aurait vu ses annotations à deux endroits — dans sa cellule *et*
    en annexe, où le tableau entier serait parti.
    """
    if old_table.tag != _TABLE or fresh_table.tag != _TABLE:
        return False

    additions = _additions(old_table)
    if not additions:
        # Rien n'a été ajouté : le tableau a donc été retouché autrement.
        return False

    rows = _rows_by_key(fresh_table)
    placed = []
    for key, column, nodes in additions:
        cells = rows.get(key)
        if cells is None or column >= len(cells):
            return False
        placed.append((cells[column], nodes))

    for cell, nodes in placed:
        cell.extend(copy(node) for node in nodes)
    return True


def _additions(table) -> list[tuple[tuple[str, ...], int, list]]:
    """Contenus ajoutés sous la donnée du script, avec la ligne et la colonne."""
    found = []
    for row in table.iterfind(_ROW):
        cells = list(row.iterfind(_CELL))
        key = _key(cells)
        for column, cell in enumerate(cells):
            extra = list(cell.iterfind(_PARAGRAPH))[1:]
            written = [node for node in extra if markers.has_content(node)]
            if written:
                found.append((key, column, written))
    return found


def _rows_by_key(table) -> dict[tuple[str, ...], list]:
    """
    Lignes du tableau neuf, par les données qu'elles portent.

    Une clé partagée par deux lignes est écartée : reposer une annotation sur
    l'une plutôt que l'autre serait un pari.
    """
    rows: dict[tuple[str, ...], list | None] = {}
    for row in table.iterfind(_ROW):
        cells = list(row.iterfind(_CELL))
        key = _key(cells)
        rows[key] = None if key in rows else cells
    return {key: cells for key, cells in rows.items() if cells is not None}


def _key(cells: list) -> tuple[str, ...]:
    """Signature d'une ligne : la donnée du script, cellule par cellule."""
    return tuple(_first_line(cell) for cell in cells)


def _first_line(cell) -> str:
    """Texte de la première ligne d'une cellule — celle que le script écrit."""
    first = next(cell.iterfind(_PARAGRAPH), None)
    return " ".join(markers.text(first).split()) if first is not None else ""
