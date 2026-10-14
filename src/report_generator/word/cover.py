"""
Cartouche de la page de garde : version, date, rédacteur, validations.

Un tableau d'une ligne d'en-tête et d'une ligne à remplir, posé en bas de la
page de garde. Il est écrit à la création du document — la date du jour
remplie, le reste laissé vide — puis appartient à l'utilisateur : à la
régénération, celui du document précédent est repris tel quel, lignes
ajoutées comprises (un historique des versions, par exemple).

La page de garde vient du template et précède la première ancre : sans cette
reprise, le cartouche rempli serait pris pour un ajout et partirait en annexe.

Le tableau se reconnaît à son titre de remplacement (`w:tblCaption`), que Word
conserve et que l'utilisateur n'a aucune raison de toucher.
"""

from datetime import datetime
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.shared import Cm, Emu
from docx.table import Table

from src.core.expressions import render
from src.report_generator.word import tables
from src.report_generator.word.values import column_width, number

CAPTION = "pbi::cartouche"

_TABLE = qn("w:tbl")
_CAPTION = qn("w:tblCaption")
_VAL = qn("w:val")

# Ordre imposé par le schéma aux enfants de `w:tblPr` : Word refuse d'ouvrir
# un document qui ne le respecte pas.
_TBLPR_ORDER = [
    qn(f"w:{tag}")
    for tag in (
        "tblStyle",
        "tblpPr",
        "tblOverlap",
        "bidiVisual",
        "tblStyleRowBandSize",
        "tblStyleColBandSize",
        "tblW",
        "jc",
        "tblCellSpacing",
        "tblInd",
        "tblBorders",
        "shd",
        "tblLayout",
        "tblCellMar",
        "tblLook",
        "tblCaption",
        "tblDescription",
    )
]


def find(document) -> Any | None:
    """Le cartouche d'un document, ou None s'il n'en porte pas."""
    if document is None:
        return None
    for table in document.element.body.iter(_TABLE):
        caption = table.find(f"{qn('w:tblPr')}/{_CAPTION}")
        if caption is not None and caption.get(_VAL) == CAPTION:
            return table
    return None


def build(
    doc, options: dict[str, Any], context: dict[str, Any], styles, text_width: int
) -> Table | None:
    """
    Écrit un cartouche neuf, détaché du corps : à l'appelant de le placer.

    Les colonnes viennent de `document.cover.table.columns` ; `{{ today }}`
    y désigne la date de génération, au format `date_format`. Une colonne
    sans `width_cm` prend sa part de la largeur du texte (`text_width`, EMU).
    """
    columns = options.get("columns") or []
    if not columns:
        return None

    today = datetime.now().strftime(str(options.get("date_format") or "%d/%m/%Y"))  # noqa: DTZ005
    context = {**context, "today": today}

    share = (Emu(text_width).cm if text_width else 16.0) / len(columns)
    widths = [column_width(column) or share for column in columns]

    table = Table(CT_Tbl.new_tbl(2, len(columns), Cm(sum(widths))), doc.part)
    style = styles.table(render(options.get("style"), context))
    if style:
        table.style = style

    tables.set_fixed_layout(table, widths)
    tables.set_table_look(table, first_row=True)
    _anchor_bottom(table)
    _set_caption(table)

    header_style = styles.paragraph(options.get("header_style") or "normal")
    value_style = styles.paragraph(options.get("value_style") or "normal")
    height = number(options.get("row_height_cm"), "row_height_cm", 0.0, float)

    header, values = table.rows
    for row in (header, values):
        tables.keep_row_together(row)
    if height:
        values.height = Cm(height)

    for index, column in enumerate(columns):
        for row, text, style in (
            (header, render(column.get("label"), context), header_style),
            (values, render(column.get("value"), context), value_style),
        ):
            cell = row.cells[index]
            cell.width = Cm(widths[index])
            tables.set_vertical_align(cell, "center")
            paragraph = cell.paragraphs[0]
            paragraph.style = style
            if text:
                paragraph.add_run(text)

    _order_properties(table)
    return table


def _anchor_bottom(table) -> None:
    """
    Pose le tableau en bas de la zone de texte, centré : un tableau flottant
    reste sur la page de son paragraphe d'ancrage, quelle que soit la hauteur
    de ce qui le précède.
    """
    position = OxmlElement("w:tblpPr")
    for key, value in {
        "leftFromText": "142",
        "rightFromText": "142",
        "topFromText": "142",
        "vertAnchor": "margin",
        "horzAnchor": "margin",
        "tblpXSpec": "center",
        "tblpYSpec": "bottom",
    }.items():
        position.set(qn(f"w:{key}"), value)
    table._tbl.tblPr.append(position)

    overlap = OxmlElement("w:tblOverlap")
    overlap.set(_VAL, "never")
    table._tbl.tblPr.append(overlap)


def _set_caption(table) -> None:
    caption = OxmlElement("w:tblCaption")
    caption.set(_VAL, CAPTION)
    table._tbl.tblPr.append(caption)


def _order_properties(table) -> None:
    """Remet les propriétés du tableau dans l'ordre du schéma."""
    properties = table._tbl.tblPr
    rank = {tag: index for index, tag in enumerate(_TBLPR_ORDER)}
    children = sorted(properties, key=lambda node: rank.get(node.tag, len(rank)))
    for child in children:
        properties.append(child)
