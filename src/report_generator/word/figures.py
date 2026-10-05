"""
Captures : l'image, ou sa place réservée ; la légende ; les pastilles.

Un bloc `image` du plan qui désigne une capture (`capture: {page, shot}`) la
cherche dans le dossier des captures, à côté du `.pbip` — là où `--captures`
les a prises, ou là où l'utilisateur les a déposées. Trouvée, elle est
insérée telle quelle, à la largeur du texte. Absente, sa place est réservée
comme avant, décrite, pour être collée à la main.

Trois choses distinctes, que le plan règle dans `rendering.image_placeholder` :

    l'image      la capture, ou « [IMAGE] Évolution du CA » à sa place
    la légende   « Figure 3 — Évolution du CA », son numéro tenu par Word
    les repères  une rangée de pastilles numérotées, flottantes (voir `shapes`)

La numérotation des figures est portée ici, d'un emplacement au suivant.
"""

from pathlib import Path
from typing import Any

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.image.image import Image
from docx.shared import Cm, Emu, Pt

from src.core.expressions import render, resolve_items
from src.report_generator.word import fields, shapes
from src.report_generator.word.body import Body
from src.report_generator.word.styles import StyleResolver
from src.report_generator.word.values import format_template, number, numbering_mode

_MARKERS = "rendering.image_placeholder.markers"
_PICTURES = "rendering.image_placeholder"

# Pixels d'écran par centimètre : une capture est prise en pixels d'écran, et
# c'est à cette taille qu'elle se lit — une petite capture n'est pas agrandie.
_SCREEN_DPCM = 96 / 2.54


class FigureWriter:
    """Écrit les emplacements de capture, et tient leur numérotation."""

    def __init__(
        self,
        body: Body,
        styles: StyleResolver,
        options: dict[str, Any],
        last_shape: int,
        text_width: int = 0,
    ):
        self.body = body
        self.styles = styles
        self.options = options
        # Largeur utile de la page, en EMU : une capture n'en déborde jamais.
        self.text_width = text_width
        self._number = 0
        # Ce qui a été inséré, et ce qui reste à coller : le bilan le dit.
        self.inserted = 0
        self.reserved = 0
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

        picture = _capture(block, context)
        if picture is not None:
            self._write_picture(picture)
        else:
            self._write_placeholder(block, description, figure)

        if self.options.get("show_caption"):
            self._write_caption(description, figure, mode)

        self._write_markers(block, context)

        if self.options.get("empty_paragraph_after"):
            self.body.add_paragraph()

    def _write_placeholder(self, block: dict[str, Any], description: str, figure: str) -> None:
        """La place de la capture, décrite, pour qu'on l'y colle à la main."""
        text = format_template(
            self.options.get("text_format", "[IMAGE] {description}"),
            f"{_PICTURES}.text_format",
            description=description,
            n=figure,
        )
        self.body.add_paragraph(text, style=self.styles.paragraph(block.get("style") or "image"))
        self.reserved += 1

    def _write_picture(self, path: Path) -> None:
        """
        La capture elle-même, centrée, à sa taille d'écran ou à celle du texte.

        Une capture plus large que la page est ramenée à la largeur du texte,
        une plus haute que `max_height_cm` à cette hauteur : une page entière
        tient sur la page, un bouton reste de la taille d'un bouton.
        """
        width, height = self._size(path)
        paragraph = self.body.add_paragraph(style=self.styles.paragraph("picture"))
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(str(path), width=width, height=height)
        self.inserted += 1

    def _size(self, path: Path) -> tuple[Emu, Emu]:
        """Dimensions de la capture dans le document, proportions gardées."""
        image = Image.from_file(str(path))
        width = Cm(image.px_width / _SCREEN_DPCM)
        height = Cm(image.px_height / _SCREEN_DPCM)

        limit_width = self.text_width or Cm(16)
        max_height = number(self.options.get("max_height_cm"), f"{_PICTURES}.max_height_cm", 18)
        scale = min(1.0, limit_width / width, Cm(max_height) / height)
        return Emu(int(width * scale)), Emu(int(height * scale))

    def summary(self) -> str:
        """« 12 capture(s) insérée(s), 3 à coller » — vide s'il n'y a eu aucune image."""
        if not self.inserted and not self.reserved:
            return ""
        text = f"{self.inserted} capture(s) insérée(s)"
        return f"{text}, {self.reserved} emplacement(s) à compléter" if self.reserved else text

    def _write_caption(self, description: str, figure: str, mode: str) -> None:
        """
        Légende numérotée de la capture.

        Le numéro est un champ Word (`SEQ`), pas un texte : supprimer une
        capture renumérote les suivantes à l'ouverture du document, sans
        reprise à la main. `numbering: fixed` le fige dans le texte, pour un
        document destiné à un lecteur qui ne recalcule pas les champs.
        """
        template = str(self.options.get("caption_format", "{description}"))
        key = f"{_PICTURES}.caption_format"
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


def _capture(block: dict[str, Any], context: dict[str, Any]) -> Path | None:
    """
    La capture que le bloc désigne, si elle est dans le dossier des captures.

    `capture: {page: ..., shot: ...}` nomme la page et la prise par leurs
    identifiants techniques — ceux dont `--captures` tire ses noms de fichier.
    Sans dossier connu (`captures` absent du contexte), rien n'est cherché.
    """
    wanted = block.get("capture")
    library = context.get("captures")
    if not isinstance(wanted, dict) or library is None:
        return None
    page, shot = render(wanted.get("page"), context), render(wanted.get("shot"), context)
    if not page or not shot:
        return None
    return library.find(page, shot)


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
