"""Génération du document Word : ouverture du template, écriture, sauvegarde."""

from typing import Any

from docx import Document

from src import console, paths
from src.config import DocConfig, render
from src.generators.word import word_app
from src.generators.word.document import DocumentBuilder, TextProvider


def generate_word_documentation(
    config: DocConfig,
    context: dict[str, Any],
    output_path: str,
    text_provider: TextProvider | None = None,
) -> str:
    """
    Écrit le document Word et retourne un message décrivant l'issue.

    Args:
        config: configuration chargée depuis config_doc_pbi.yaml
        context: données exposées au plan (report, model, inputs, styles)
        output_path: chemin du .docx généré
        text_provider: callback optionnel permettant à l'utilisateur de
            modifier les textes des blocs `editable`
    """
    template_path = paths.find(render(config.document.get("template"), context))

    try:
        doc = Document(template_path)
    except Exception as e:  # noqa: BLE001
        return f"ERREUR : impossible de charger le template '{template_path}' — {e}"

    DocumentBuilder(doc, config, context, text_provider).build()

    try:
        doc.save(output_path)
    except OSError as e:
        return f"ERREUR : impossible d'enregistrer le document — {e}"

    if (config.rendering.get("table_of_contents") or {}).get("update_with_word"):
        console.info(word_app.refresh_fields(output_path))

    return f"Documentation Word générée : '{output_path}'"
