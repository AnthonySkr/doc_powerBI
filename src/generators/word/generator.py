"""Génération du document Word : lecture du précédent, écriture, sauvegarde."""

import os
import shutil
from datetime import datetime
from typing import Any

from docx import Document

from src import console, paths
from src.config import DocConfig, render
from src.generators.word import word_app
from src.generators.word.document import DocumentBuilder, TextProvider
from src.merge import ChangeLog, apply_merge, read_previous


def generate_word_documentation(
    config: DocConfig,
    context: dict[str, Any],
    output_path: str,
    text_provider: TextProvider | None = None,
) -> ChangeLog:
    """
    Écrit le document Word et retourne le bilan des changements.

    Si une documentation existe déjà à `output_path`, elle est lue puis
    comparée au rapport actuel : les textes rédigés par l'utilisateur sont
    repris dans le document neuf. L'ancien fichier n'est jamais modifié — il
    est archivé avant d'être remplacé.

    Args:
        config: configuration chargée depuis config_doc_pbi.yaml
        context: données exposées au plan (report, model, inputs, styles)
        output_path: chemin du .docx généré
        text_provider: callback optionnel permettant à l'utilisateur de
            modifier les textes des blocs `editable`
    """
    merge_options = config.merge
    previous = read_previous(output_path) if merge_options.get("enabled", True) else None

    template_path = render(config.document.get("template"), context)
    try:
        doc = Document(template_path)
    except Exception as e:  # noqa: BLE001
        raise DocumentError(f"Impossible de charger le template '{template_path}' — {e}") from e

    # Le plan peut conditionner une section à `merge.is_update`.
    context = {**context, "merge": {"is_update": bool(previous and previous.exists)}}

    builder = DocumentBuilder(doc, config, context, text_provider, previous)
    builder.build()

    log = builder.merge.log
    if previous is not None and previous.exists:
        # Le document neuf porte ses ancres : il est maintenant recomposé en
        # suivant l'ordre du document précédent, dont seuls les contenus
        # produits par le script sont remplacés.
        apply_merge(doc, previous, merge_options, log)
    archived = ""
    if previous is not None and previous.exists:
        log.removed = previous.removed(log.written_ids)
        archived = _archive(output_path, merge_options)

    try:
        doc.save(output_path)
    except OSError as e:
        _restore(archived, output_path)
        raise DocumentError(f"Impossible d'enregistrer le document — {e}") from e

    console.info(f"Documentation Word générée : '{output_path}'")

    if (config.rendering.get("table_of_contents") or {}).get("update_with_word"):
        console.info(word_app.refresh_fields(output_path))

    return log


class DocumentError(Exception):
    """Le document n'a pas pu être produit."""


def _archive(output_path: str, options: dict[str, Any]) -> str:
    """
    Déplace la documentation existante dans un sous-dossier horodaté.

    Le document précédent n'est donc jamais écrasé : en cas de fusion
    inattendue, la version d'origine reste récupérable telle quelle.
    """
    if not options.get("backup", True):
        return ""

    directory = os.path.join(
        os.path.dirname(output_path), str(options.get("backup_dir") or ".versions")
    )
    os.makedirs(directory, exist_ok=True)

    name, extension = os.path.splitext(os.path.basename(output_path))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archived = os.path.join(directory, f"{name}_{stamp}{extension}")

    try:
        shutil.move(output_path, archived)
    except OSError as e:
        raise DocumentError(
            f"Impossible d'archiver la version précédente ({e}). "
            "Le document existant n'a pas été touché."
        ) from e

    console.info(f"Version précédente archivée dans {os.path.basename(directory)}/")
    return archived


def _restore(archived: str, output_path: str) -> None:
    """Remet la version précédente en place si l'écriture du document a échoué."""
    if archived and os.path.isfile(archived) and not os.path.exists(output_path):
        shutil.move(archived, output_path)
