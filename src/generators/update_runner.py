"""
Exécution du mode « mise à jour » : le document existant est complété,
jamais réécrit.

Le script génère d'abord, en mémoire, le document tel qu'il serait produit
aujourd'hui, puis le compare au fichier déjà présent et n'y reporte que les
différences.
"""

from typing import Any

from docx import Document

from src.doc_config import DocConfig, render
from src.generators.doc_updater import UpdateReport, backup_document, update_document
from src.generators.word_generator import (
    TextProvider,
    build_document,
    heading_style_levels,
    refresh_fields_with_word,
    style_id,
)


def update_existing_documentation(
    config: DocConfig,
    context: dict[str, Any],
    output_path: str,
    text_provider: TextProvider | None = None,
    dry_run: bool = False,
) -> str:
    """
    Met à jour une documentation déjà rédigée.

    Args:
        output_path: document existant, conservé et complété
        dry_run: n'écrit rien, se contente d'afficher les différences
    """
    options = config.rendering.get("update") or {}
    if not options.get("enabled", True):
        return (
            f"Le document '{output_path}' existe déjà et la mise à jour est désactivée "
            "(rendering.update.enabled) — utiliser --force pour le régénérer"
        )

    try:
        fresh_doc, tracked_blocks, item_bookmarks = build_document(config, context, text_provider)
    except OSError as e:
        return f"ERREUR : template illisible. Détails : {e}"

    try:
        existing_doc = Document(output_path)
    except Exception as e:  # noqa: BLE001
        return f"ERREUR : document existant illisible '{output_path}'. Détails : {e}"

    tracked_ids, review_ids = config.tracked_block_ids()
    heading_styles = heading_style_levels(existing_doc, config)
    todo_style = style_id(existing_doc, config, "todo")

    # Les notes reprennent le style « à compléter » du template : Word attend
    # l'identifiant du style, pas son nom.
    labels = options.get("labels") or {}
    options = {
        **options,
        "note_style_id": _note_style_id(existing_doc, config, options),
        "ignored_run_styles": [style_id(existing_doc, config, "technical_id")],
    }
    kinds = {
        name: labels.get(raw.split(":")[0], raw.split(":")[0])
        for name, raw in item_bookmarks.items()
    }

    report = update_document(
        existing_doc,
        fresh_doc,
        config,
        context,
        heading_styles,
        tracked_blocks,
        review_ids,
        todo_style,
        kinds,
        options,
    )

    _print_report(report, tracked_ids, review_ids)

    if not report.applied:
        return f"Document déjà à jour : '{output_path}'"

    if dry_run:
        return f"Simulation : '{output_path}' n'a pas été modifié"

    if options.get("backup", True):
        saved = backup_document(output_path, options.get("backup_suffix", ".bak"))
        if saved:
            print(f"  Sauvegarde : '{saved}'")

    try:
        existing_doc.save(output_path)
    except Exception as e:  # noqa: BLE001
        return f"Erreur lors de l'enregistrement du document : {e}"

    if (config.rendering.get("table_of_contents") or {}).get("update_with_word"):
        print(f"  {refresh_fields_with_word(output_path)}")

    return (
        f"Document mis à jour : '{output_path}' "
        f"({len(report.added)} ajout(s), {len(report.changed)} changement(s))"
    )


def _note_style_id(doc, config: DocConfig, options: dict[str, Any]) -> str:
    """Identifiant du style de paragraphe utilisé pour les notes de suivi."""
    name = render(options.get("note_style") or "{{ styles.todo }}", {"styles": config.styles})
    for style in doc.styles:
        if style.name == name:
            return style.style_id
    return "Normal"


def _print_report(report: UpdateReport, tracked: set[str], review: set[str]) -> None:
    """Affiche le bilan de la comparaison."""
    for line in report.lines():
        print(line)
    if report.changed and review:
        print("  Les textes rédigés ont été surlignés : à relire puis à valider")
    if not tracked:
        print("  Aucun bloc suivi dans le plan (`track:`) : seuls les ajouts sont détectés")
