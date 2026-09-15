"""
Emplacements de captures : le repère, la légende et les pastilles.

Le script ne colle pas les images — personne ne sait les produire depuis un
fichier .pbip. Il réserve leur place, la décrit, la numérote, et pose sous elle
les repères qu'il ne restera qu'à faire glisser sur la capture une fois
celle-ci collée.

Trois choses distinctes, que le plan règle dans `rendering.image_placeholder` :

    le repère    « [IMAGE] Évolution du CA », dans le style du plan
    la légende   « Figure 3 — Évolution du CA », son numéro tenu par Word
    les repères  une rangée de pastilles numérotées, flottantes (voir `shapes`)

La numérotation des figures est portée ici, d'un emplacement au suivant.
"""

from typing import Any

from docx.shared import Cm, Pt

from src.core.expressions import render, resolve_items
from src.report_generator.word import fields, shapes
from src.report_generator.word.body import Body
from src.report_generator.word.styles import StyleResolver
from src.report_generator.word.values import format_template, number, numbering_mode

_MARKERS = "rendering.image_placeholder.markers"


class FigureWriter:
    """Écrit les emplacements de capture, et tient leur numérotation."""

    def __init__(self, body: Body, styles: StyleResolver, options: dict[str, Any], last_shape: int):
        self.body = body
        self.styles = styles
        self.options = options
        self._number = 0
        # Word refuse deux formes de même identifiant : la numérotation des
        # repères reprend au-dessus de ce que le template contient déjà.
        self._shape_id = last_shape

    def write(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        """Réserve l'emplacement d'une capture, avec sa description."""
        description = render(block.get("description"), context)
        mode = numbering_mode(self.options.get("numbering"))

        if mode != "none":
            self._number += 1
        figure = str(self._number) if mode != "none" else ""

        text = format_template(
            self.options.get("text_format", "[IMAGE] {description}"),
            "rendering.image_placeholder.text_format",
            description=description,
            n=figure,
        )
        self.body.add_paragraph(text, style=self.styles.paragraph(block.get("style") or "image"))

        if self.options.get("show_caption"):
            self._write_caption(description, figure, mode)

        self._write_markers(block, context)

        if self.options.get("empty_paragraph_after"):
            self.body.add_paragraph()

    def _write_caption(self, description: str, figure: str, mode: str) -> None:
        """
        Légende numérotée de la capture.

        Le numéro est un champ Word (`SEQ`), pas un texte : supprimer une
        capture renumérote les suivantes à l'ouverture du document, sans
        reprise à la main. `numbering: fixed` le fige dans le texte, pour un
        document destiné à un lecteur qui ne recalcule pas les champs.
        """
        template = str(self.options.get("caption_format", "{description}"))
        key = "rendering.image_placeholder.caption_format"
        values = {"description": description, "n": figure}
        paragraph = self.body.add_paragraph(style=self.styles.paragraph("caption"))

        head, field, tail = template.partition("{n}")
        if mode != "auto" or not field:
            paragraph.add_run(format_template(template, key, **values))
            return

        paragraph.add_run(format_template(head, key, **values))
        sequence = str(self.options.get("sequence") or "Figure")
        fields.write_sequence_field(paragraph, sequence, figure)
        paragraph.add_run(format_template(tail, key, **values))

    def _write_markers(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        """
        Repères numérotés à faire glisser sur la capture.

        Les numéros sont ceux du tableau qui suit la capture — le plan désigne
        la même liste. Ils sont posés en rangée sous l'emplacement, et n'ont
        plus qu'à être déplacés un à un sur l'image : ce sont des formes
        flottantes, elles ne bousculent rien en route.
        """
        plan = block.get("markers")
        if not plan:
            return

        labels = _marker_labels(plan, context)
        if not labels:
            return

        look = self.options.get("markers") or {}
        paragraph = self.body.add_paragraph(style=self.styles.paragraph(look.get("style")))
        self._shape_id = shapes.draw_row(paragraph, labels, _marker_style(look), self._shape_id)


def _marker_labels(plan: dict[str, Any], context: dict[str, Any]) -> list[str]:
    """Numéros portés par les repères, dans l'ordre du tableau qui les explique."""
    item = plan.get("item") or "item"
    template = plan.get("label") or f"{{{{ {item}.number }}}}"
    labels = (
        render(template, {**context, item: value})
        for value in resolve_items(plan.get("over"), context)
    )
    return [label for label in labels if label]


def _marker_style(look: dict[str, Any]) -> shapes.MarkerStyle:
    """Traduit `rendering.image_placeholder.markers` en aspect de repères."""
    return shapes.MarkerStyle(
        size=Cm(number(look.get("size_cm"), f"{_MARKERS}.size_cm", 0.62)),
        spacing=Cm(number(look.get("spacing_cm"), f"{_MARKERS}.spacing_cm", 0.9)),
        line=Cm(number(look.get("line_cm"), f"{_MARKERS}.line_cm", 0.9)),
        per_row=max(number(look.get("per_row"), f"{_MARKERS}.per_row", 12, int), 1),
        shape=str(look.get("shape") or "ellipse"),
        fill=str(look.get("fill") or "0070C0"),
        text_color=str(look.get("text_color") or "FFFFFF"),
        font_size=Pt(number(look.get("font_size_pt"), f"{_MARKERS}.font_size_pt", 9)),
    )
