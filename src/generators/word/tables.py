"""
Réglages OOXML des tableaux que python-docx n'expose pas.

Word se fie à la grille du tableau (`w:tblGrid`) et à sa mise en forme
conditionnelle (`w:tblLook`) : sans ces réglages, les largeurs déclarées sur
les cellules sont ignorées et le style nommé du template n'est pas appliqué.
"""

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm


def set_fixed_layout(table, widths: list[float | None]) -> None:
    """Fige la mise en page du tableau et reporte les largeurs (cm) sur la grille."""
    layout = _get_or_add(table._tbl.tblPr, "w:tblLayout")
    layout.set(qn("w:type"), "fixed")

    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is None:
        return
    for column, width in zip(grid.findall(qn("w:gridCol")), widths):
        if width is not None:
            column.set(qn("w:w"), str(int(round(Cm(width).twips))))  # noqa: RUF046


def set_table_look(table, first_row: bool) -> None:
    """
    Active la mise en forme conditionnelle du style de tableau : ligne
    d'en-tête colorée et lignes alternées, sans bandes verticales.
    """
    look = _get_or_add(table._tbl.tblPr, "w:tblLook")
    look.set(qn("w:val"), "0620" if first_row else "0420")
    for key, value in {
        "firstRow": "1" if first_row else "0",
        "lastRow": "0",
        "firstColumn": "0",
        "lastColumn": "0",
        "noHBand": "0",
        "noVBand": "1",
    }.items():
        look.set(qn("w:" + key), value)


def repeat_header_row(row) -> None:
    """Répète la ligne d'en-tête en haut de chaque page."""
    _get_or_add(row._tr.get_or_add_trPr(), "w:tblHeader")


def keep_row_together(row) -> None:
    """Empêche une ligne d'être coupée par un saut de page."""
    _get_or_add(row._tr.get_or_add_trPr(), "w:cantSplit")


def set_vertical_align(cell, alignment: str) -> None:
    """Alignement vertical du contenu d'une cellule."""
    if alignment:
        _get_or_add(cell._tc.get_or_add_tcPr(), "w:vAlign").set(qn("w:val"), alignment)


def _get_or_add(parent, tag: str):
    """Retourne l'enfant `tag` du nœud, en le créant s'il n'existe pas encore."""
    element = parent.find(qn(tag))
    if element is None:
        element = OxmlElement(tag)
        parent.append(element)
    return element
