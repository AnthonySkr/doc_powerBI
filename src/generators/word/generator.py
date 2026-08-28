"""Génération du document Word : lecture du précédent, écriture, sauvegarde."""

import os
import shutil
from datetime import datetime
from typing import Any

from docx import Document

from src import console, paths
from src.config import DocConfig, render
from src.generators.word import word_app
from src.generators.word.document import DocumentBuilder, DocumentError, TextProvider
from src.merge import ChangeLog, apply_merge, markers, orphans, read_previous


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

    try:
        doc = Document(_template_path(config, context))
    except DocumentError:
        raise
    except Exception as e:
        raise DocumentError(f"Template illisible — {e}") from e

    # Le plan peut conditionner une section à `merge.is_update`.
    context = {**context, "merge": {"is_update": bool(previous and previous.exists)}}

    builder = DocumentBuilder(doc, config, context, text_provider, previous)
    builder.build()

    log = builder.merge.log
    if previous is not None and previous.exists:
        # Le document neuf porte ses ancres : il est maintenant recomposé en
        # suivant l'ordre du document précédent, dont seuls les contenus
        # produits par le script sont remplacés. Ce qui n'a pas pu être
        # replacé est rassemblé en annexe plutôt que perdu.
        orphans.report(apply_merge(doc, previous, merge_options, log, builder.styles))
    archived = ""
    if previous is not None and previous.exists:
        log.removed = previous.removed(log.written_ids | log.renamed_ids)
        archived = _archive(output_path, merge_options)

    # Les marqueurs recopiés depuis le document précédent n'ont pas forcément
    # été écrits par cette version : on les resserre tous avant d'enregistrer.
    markers.collapse_all(doc)

    try:
        doc.save(output_path)
    except Exception as e:
        # Toute cause vaut restauration : la version précédente vient d'être
        # déplacée, elle doit revenir quoi qu'il soit arrivé à l'écriture.
        _restore(archived, output_path)
        raise DocumentError(f"Impossible d'enregistrer le document — {e}") from e

    console.info(f"Documentation Word générée : '{output_path}'")

    if (config.rendering.get("table_of_contents") or {}).get("update_with_word"):
        console.info(word_app.refresh_fields(output_path))

    return log


def _template_path(config: DocConfig, context: dict[str, Any]) -> str:
    """
    Localise le template Word désigné par la configuration.

    Le nom déclaré est relatif : il est cherché à côté de la configuration qui
    le nomme, puis à côté de l'exécutable. Le dossier courant ne suffit pas —
    un exécutable ouvert par glisser-déposer en hérite d'un quelconque.
    """
    name = render(config.document.get("template"), context)
    if not name:
        raise DocumentError("Aucun template déclaré dans `document.template`.")

    near = os.path.dirname(os.path.abspath(config.path)) if config.path else ""
    path = paths.find(name, near=near)
    if os.path.isfile(path):
        return path

    cherches = "\n".join(f"      {os.path.abspath(c)}" for c in paths.candidates(name, near))
    raise DocumentError(
        f"Template introuvable : '{name}'. Cherché ici :\n{cherches}\n"
        f"      Placez-le à côté de {os.path.basename(config.path) or 'la configuration'}."
    )


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
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
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
    """
    Remet la version précédente en place lorsque l'écriture a échoué.

    Un enregistrement interrompu laisse un fichier incomplet : il est écrasé,
    sans quoi la version précédente resterait dans `.versions` et l'utilisateur
    se retrouverait devant un document illisible.
    """
    if not archived or not os.path.isfile(archived):
        return
    try:
        os.replace(archived, output_path)
    except OSError as e:
        console.warn(
            f"Version précédente non restaurée ({e}) — elle reste dans "
            f"{os.path.basename(os.path.dirname(archived))}/"
        )
