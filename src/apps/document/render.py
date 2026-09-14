"""
L'écriture du document, à partir du fichier d'échange et de rien d'autre.

C'est le point d'entrée programmatique de l'application : le pipeline comme la
ligne de commande passent par ici. Ce qui vient d'avant — le rapport lu, les
captures prises — est déjà dans l'échange ; ce qui vient de l'utilisateur — les
réponses aux questions, la réécriture des textes — est passé en argument.
"""

import os
from dataclasses import dataclass
from typing import Any

from src.apps.document.context import build_context
from src.apps.document.word import DocumentError, TextProvider, generate_word_documentation
from src.shared import console
from src.shared.config import DEFAULT_OUTPUT_DIR, DocConfig, render
from src.shared.exchange import Exchange

__all__ = ["DocumentResult", "output_directory", "write_document"]


@dataclass
class DocumentResult:
    """Ce que l'écriture a produit."""

    path: str
    summary: str
    details: list[str]
    # Mesures du modèle que le document ne documente pas — nommées en fin
    # d'exécution, pour que l'écart soit vu plutôt que subi.
    undocumented: list[str]


def output_directory(exchange: Exchange, config: DocConfig, inputs: dict[str, Any]) -> str:
    """Dossier de sortie déclaré par le plan, une fois les réponses connues."""
    context = {"report": exchange.report, "inputs": inputs}
    return render(config.document.get("output_dir"), context) or DEFAULT_OUTPUT_DIR


def write_document(
    exchange: Exchange,
    config: DocConfig,
    inputs: dict[str, Any],
    output_dir: str,
    rewrite: TextProvider | None = None,
) -> DocumentResult:
    """Écrit le document Word et retourne son bilan."""
    report = exchange.report
    context = build_context(report, report.all_measures, config, inputs)
    output_name = render(config.document.get("output_name"), context) or (
        f"documentation_{report.name}.docx"
    )

    # Le dossier de sortie appartient à qui écrit dedans : lancée seule, cette
    # application n'a personne d'autre pour le créer.
    os.makedirs(output_dir, exist_ok=True)
    log = generate_word_documentation(
        config, context, os.path.join(output_dir, output_name), rewrite
    )
    return DocumentResult(
        path=os.path.join(output_dir, output_name),
        summary=log.summary(),
        details=log.details(),
        undocumented=list(report.undocumented_measures),
    )


def report_result(result: DocumentResult) -> None:
    """Affiche le bilan de l'écriture — commun au pipeline et à l'app seule."""
    console.blank()
    console.done(result.summary)
    for line in result.details:
        console.detail(line)

    if not result.undocumented:
        return

    console.blank()
    console.info(
        f"{len(result.undocumented)} mesure(s) du modèle non documentée(s) — non utilisée(s) :"
    )
    for name in result.undocumented:
        console.detail(f"· {name}")


# Réexporté pour que l'appelant n'ait pas à connaître le paquet `word`.
__all__ += ["DocumentError", "report_result"]
