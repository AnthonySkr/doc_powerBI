"""
Génération du document Word à partir du plan décrit dans config_doc_pbi.yaml.

Le générateur ne connaît aucune structure de document : il parcourt les
`sections` / `blocks` de la configuration et écrit ce qu'elles décrivent.
"""

import hashlib
import re
from collections.abc import Callable
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm

from src.doc_config import DocConfig, evaluate, render, render_list, resolve

TextProvider = Callable[[dict[str, Any], str], str]


def generate_word_documentation(
    config: DocConfig,
    context: dict[str, Any],
    output_path: str,
    text_provider: TextProvider | None = None,
) -> str:
    """
    Écrit le document Word.

    Args:
        config: configuration chargée depuis config_doc_pbi.yaml
        context: données exposées au plan (report, model, inputs, styles)
        output_path: chemin du .docx généré
        text_provider: callback optionnel permettant à l'utilisateur de
            modifier les textes des blocs `editable`
    """
    template_path = render(config.document.get("template"), context)

    try:
        doc = Document(template_path)
    except Exception as e:  # noqa: BLE001
        return f"ERREUR : Impossible de charger le template '{template_path}'. Détails : {e}"

    builder = _DocumentBuilder(doc, config, context, text_provider)
    builder.build()

    try:
        doc.save(output_path)
        return f"Documentation Word générée : '{output_path}'"
    except Exception as e:  # noqa: BLE001
        return f"Erreur lors de la sauvegarde du document : {e}"


# ==============================================================================
#  Construction du document
# ==============================================================================


class _DocumentBuilder:
    def __init__(
        self,
        doc: Document,  # type: ignore[valid-type]
        config: DocConfig,
        context: dict[str, Any],
        text_provider: TextProvider | None = None,
    ):
        self.doc = doc
        self.config = config
        self.context = context
        self.text_provider = text_provider

        self._available_styles = {s.name for s in doc.styles}
        self._bookmark_id = 0
        self._figure_number = 0

        self._block_writers = {
            "paragraph": self._write_paragraph_block,
            "image": self._write_image_block,
            "user_fill": self._write_user_fill_block,
            "property": self._write_property_block,
            "table": self._write_table_block,
            "loop": self._write_loop_block,
        }

    # ── Point d'entrée ────────────────────────────────────────────
    def build(self) -> None:
        self._write_cover()
        self._write_properties()
        for section in self.config.sections:
            self._write_section(section, self.context)

    # ── Page de garde et propriétés ───────────────────────────────
    def _write_cover(self) -> None:
        cover = self.config.document.get("cover") or {}
        placeholder = render(cover.get("placeholder"), self.context)
        text = render(cover.get("text"), self.context)
        if not placeholder or not text:
            return

        for paragraph in self.doc.paragraphs:
            if placeholder in paragraph.text:
                for run in list(paragraph.runs):
                    run._element.getparent().remove(run._element)
                self._write_multiline_runs(paragraph, text, bold=bool(cover.get("bold", True)))
                return

    def _write_properties(self) -> None:
        properties = self.config.document.get("properties") or {}
        for key, value in properties.items():
            if hasattr(self.doc.core_properties, key):
                setattr(self.doc.core_properties, key, render(value, self.context))

    # ── Sections ──────────────────────────────────────────────────
    def _write_section(self, section: dict[str, Any], context: dict[str, Any]) -> None:
        if section.get("generate") is False or section.get("source") == "template":
            return
        if not evaluate(section.get("when"), context):
            return

        if self._needs_page_break(section):
            self.doc.add_page_break()

        title = render(section.get("title"), context)
        if title:
            level = int(section.get("level", 1))
            paragraph = self.doc.add_paragraph(title, style=self._style(f"heading_{level}"))
            bookmark = section.get("bookmark")
            if bookmark:
                self._add_bookmark(paragraph, render(bookmark, context))

        for block in section.get("blocks") or []:
            self._write_block(block, context)

        for child in section.get("sections") or []:
            self._write_section(child, context)

    def _needs_page_break(self, section: dict[str, Any]) -> bool:
        if "page_break_before" in section:
            return bool(section["page_break_before"])
        return bool(self.config.rendering.get("page_break_before_heading_1")) and (
            int(section.get("level", 1)) == 1
        )

    # ── Blocs ─────────────────────────────────────────────────────
    def _write_block(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        if not evaluate(block.get("when"), context):
            return

        writer = self._block_writers.get(block.get("type", ""))
        if writer is None:
            print(f"  Type de bloc inconnu ignoré : '{block.get('type')}' ({block.get('id')})")
            return
        writer(block, context)

    def _write_paragraph_block(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        text = render(block.get("text"), context)
        if block.get("editable") and self.text_provider is not None:
            text = self.text_provider(block, text)
        if not text:
            return
        paragraph = self.doc.add_paragraph(style=self._style(block.get("style") or "normal"))
        self._write_multiline_runs(paragraph, text)

    def _write_image_block(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        options = self.config.rendering["image_placeholder"]
        description = render(block.get("description"), context)

        if options.get("numbering"):
            self._figure_number += 1

        text = str(options.get("text_format", "[IMAGE] {description}")).format(
            description=description, n=self._figure_number
        )
        self.doc.add_paragraph(text, style=self._style(block.get("style") or "image"))

        if options.get("show_caption"):
            caption = str(options.get("caption_format", "{description}")).format(
                description=description, n=self._figure_number
            )
            self.doc.add_paragraph(caption, style=self._style("caption"))

        if options.get("empty_paragraph_after"):
            self.doc.add_paragraph()

    def _write_user_fill_block(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        options = self.config.rendering["user_fill"]
        text = ""
        if options.get("show_placeholder"):
            text = render(
                block.get("placeholder_text") or options.get("placeholder_text"),
                context,
            )
        self.doc.add_paragraph(text, style=self._style(block.get("style") or "normal"))

    def _write_property_block(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        options = self.config.rendering["property"]

        label = render(block.get("label"), context)
        if label:
            self.doc.add_paragraph(
                label,
                style=self._style(block.get("label_style") or options.get("label_style")),
            )

        value_style = self._style(block.get("value_style") or options.get("value_style"))
        fallback = render(block.get("fallback"), context)

        if "value_list" in block:
            values = render_list(block.get("value_list"), context)
            if values:
                for value in values:
                    self.doc.add_paragraph(value, style=value_style)
            elif fallback:
                self.doc.add_paragraph(fallback, style=self._style("normal"))
        else:
            value = render(block.get("value"), context)
            if value:
                paragraph = self.doc.add_paragraph(style=value_style)
                self._write_multiline_runs(paragraph, value)
            elif fallback:
                self.doc.add_paragraph(fallback, style=self._style("normal"))

        if options.get("empty_paragraph_after"):
            self.doc.add_paragraph()

    def _write_table_block(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        columns = block.get("columns") or []
        rows = render_list_of_items(block.get("over"), context)
        if not columns or not rows:
            return

        table = self.doc.add_table(rows=0, cols=len(columns))
        self._apply_table_style(table, render(block.get("style"), context))
        table.autofit = bool(block.get("autofit", False))

        if block.get("header"):
            labels = block.get("header_labels") or [c.get("id", "") for c in columns]
            header_cells = table.add_row().cells
            for cell, label in zip(header_cells, labels):
                cell.text = render(label, context)
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True

        item_name = block.get("item") or "item"
        for row_item in rows:
            row_context = {**context, item_name: row_item}
            cells = table.add_row().cells
            for cell, column in zip(cells, columns):
                self._fill_table_cell(cell, column, row_context)

        self._set_column_widths(table, columns)
        self.doc.add_paragraph()

    def _fill_table_cell(self, cell, column: dict[str, Any], context: dict[str, Any]) -> None:
        text = render(column.get("value"), context)
        paragraph = cell.paragraphs[0]

        hyperlink = column.get("hyperlink") or {}
        link_text = render(hyperlink.get("text"), context) if hyperlink else ""
        links_enabled = self.config.rendering["links"].get("enabled", True)

        if (
            hyperlink
            and links_enabled
            and link_text
            and evaluate(hyperlink.get("when"), context)
            and link_text in text
        ):
            target = self._bookmark_for(render(hyperlink.get("target"), context))
            before, _, after = text.partition(link_text)
            if before:
                paragraph.add_run(before)
            self._add_hyperlink(paragraph, link_text, target)
            if after:
                paragraph.add_run(after)
        else:
            paragraph.add_run(text)

    def _write_loop_block(self, block: dict[str, Any], context: dict[str, Any]) -> None:
        items = render_list_of_items(block.get("over"), context)
        if not items:
            return

        item_name = block.get("item") or "item"
        section = block.get("section")
        blocks = block.get("blocks")

        for item in items:
            item_context = {**context, item_name: item}
            if section:
                self._write_section(section, item_context)
            for inner in blocks or []:
                self._write_block(inner, item_context)

    # ── Utilitaires de mise en forme ──────────────────────────────
    def _style(self, key: str | None) -> str:
        """Résout une clé de style (ou un `{{ styles.x }}`) en style Word existant."""
        if not key:
            key = "normal"

        name = render(key, self.context) if "{{" in str(key) else self.config.styles.get(key, key)
        if name in self._available_styles:
            return name

        fallback = self.config.styles.get("fallback", "Normal")
        if name and name != fallback:
            print(f"  Style '{name}' absent du template — remplacé par '{fallback}'")
        return fallback if fallback in self._available_styles else "Normal"

    def _apply_table_style(self, table, style_name: str) -> None:
        if style_name and style_name in self._available_styles:
            try:
                table.style = style_name
            except (KeyError, ValueError) as e:
                print(f"  Style de tableau '{style_name}' non applicable : {e}")

    def _set_column_widths(self, table, columns: list[dict[str, Any]]) -> None:
        for index, column in enumerate(columns):
            width = column.get("width_cm")
            if not width:
                continue
            for row in table.rows:
                row.cells[index].width = Cm(float(width))

    def _write_multiline_runs(self, paragraph, text: str, bold: bool = False) -> None:
        """Écrit un texte en gérant les retours à la ligne."""
        lines = text.split("\n")
        for index, line in enumerate(lines):
            run = paragraph.add_run(line)
            run.bold = bold
            if index < len(lines) - 1:
                run.add_break()

    # ── Signets et liens internes ─────────────────────────────────
    def _bookmark_for(self, raw_name: str) -> str:
        """Nom de signet d'une cible (`measure:Chiffre d'affaires` → signet Word)."""
        prefix = self.config.rendering["links"].get("bookmark_prefix", "") or ""
        return _bookmark_name(prefix + (raw_name or ""))

    def _add_bookmark(self, paragraph, raw_name: str) -> None:
        name = self._bookmark_for(raw_name)
        if not name:
            return

        self._bookmark_id += 1
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), str(self._bookmark_id))
        start.set(qn("w:name"), name)
        paragraph._p.insert(0, start)

        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(self._bookmark_id))
        paragraph._p.append(end)

    def _add_hyperlink(self, paragraph, text: str, bookmark: str) -> None:
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("w:anchor"), bookmark)

        run = OxmlElement("w:r")
        run_properties = OxmlElement("w:rPr")
        style = OxmlElement("w:rStyle")
        style.set(qn("w:val"), self.config.rendering["links"].get("style", "Hyperlink"))
        run_properties.append(style)
        run.append(run_properties)

        text_element = OxmlElement("w:t")
        text_element.text = text
        text_element.set(qn("xml:space"), "preserve")
        run.append(text_element)

        hyperlink.append(run)
        paragraph._p.append(hyperlink)


# ==============================================================================
#  Helpers
# ==============================================================================


def render_list_of_items(expression: Any, context: dict[str, Any]) -> list[Any]:
    """Résout l'expression `over:` d'une boucle ou d'un tableau."""
    if not expression:
        return []
    if isinstance(expression, (list, tuple)):
        return list(expression)

    path = str(expression).strip()
    if path.startswith("{{"):
        path = path.strip("{} ")

    value = resolve(path, context)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return list(value.values())
    return [value]


def _bookmark_name(name: str) -> str:
    """
    Nom de signet valide pour Word : lettres, chiffres et underscores,
    40 caractères maximum, ne commençant pas par un chiffre.

    Au-delà de 40 caractères le nom est tronqué et suffixé d'une empreinte,
    pour que deux mesures au préfixe identique ne partagent pas le même signet.
    """
    cleaned = re.sub(r"\W+", "_", name or "", flags=re.UNICODE).strip("_")
    if not cleaned:
        return ""
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if len(cleaned) > 40:
        digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:7]
        cleaned = f"{cleaned[:32]}_{digest}"
    return cleaned
