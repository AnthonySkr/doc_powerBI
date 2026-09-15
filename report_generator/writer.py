"""
L'écriture du document, à partir des métadonnées et de rien d'autre.

C'est le point d'entrée du module : ce qui vient d'avant — le rapport lu, les
captures prises — est déjà dans le `PowerBiMetadata` ; ce qui vient de
l'utilisateur — les réponses aux questions, la réécriture des textes — est
passé en argument.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core import console
from core.config import DEFAULT_OUTPUT_DIR, DocConfig
from core.expressions import render
from core.models import PowerBiMetadata
from core.prompts import TextProvider
from report_generator.context import build_context
from report_generator.word import DocumentError, generate_word_documentation

__all__ = [
    "DocumentError",
    "DocumentResult",
    "output_directory",
    "report_result",
    "write_document",
]


@dataclass
class DocumentResult:
    """Ce que l'écriture a produit."""

    path: Path
    summary: str
    details: list[str]
    # Mesures du modèle que le document ne documente pas — nommées en fin
    # d'exécution, pour que l'écart soit vu plutôt que subi.
    undocumented: list[str]


def output_directory(metadata: PowerBiMetadata, config: DocConfig, inputs: dict[str, Any]) -> str:
    """Dossier de sortie déclaré par le plan, une fois les réponses connues."""
    context = {"report": metadata.report, "inputs": inputs}
    return render(config.document.get("output_dir"), context) or DEFAULT_OUTPUT_DIR


def write_document(
    metadata: PowerBiMetadata,
    config: DocConfig,
    inputs: dict[str, Any],
    output_dir: str | Path,
    rewrite: TextProvider | None = None,
) -> DocumentResult:
    """Écrit le document Word et retourne son bilan."""
    report = metadata.report
    context = build_context(report, report.all_measures, config, inputs)
    name = render(config.document.get("output_name"), context) or (
        f"documentation_{report.name}.docx"
    )

    # Le dossier de sortie appartient à qui écrit dedans.
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name

    log = generate_word_documentation(config, context, str(path), rewrite)
    return DocumentResult(
        path=path,
        summary=log.summary(),
        details=log.details(),
        undocumented=list(report.undocumented_measures),
    )


def report_result(result: DocumentResult) -> None:
    """Affiche le bilan de l'écriture."""
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
