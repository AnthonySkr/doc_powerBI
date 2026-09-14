"""
L'application « document », à lancer seule.

    python -m src.apps.document
    python -m src.apps.document -i .echange/1-rapport.json --keep

Elle lit le fichier d'échange et écrit le .docx. Sans Power BI, sans `.pbip` :
mettre au point un plan de document se fait donc sur des données déjà lues, en
relançant celle-ci autant de fois qu'il faut.

Les réponses aux questions de `inputs:` sont celles que la dernière génération
a retenues (voir `cli.answers`) ; cette application ne pose aucune question.
"""

import argparse
import os
import sys

from src import __version__
from src.apps.document.render import (
    DocumentError,
    output_directory,
    report_result,
    write_document,
)
from src.shared import answers, console
from src.shared.config import DEFAULT_CONFIG_PATH, load_config
from src.shared.exchange import ExchangeError, discard, read
from src.shared.inputs import base_context, default_inputs

# Ce que cette application lit. Elle n'écrit pas de fichier d'échange : elle est
# la dernière de la chaîne.
INPUT_NAME = "2-captures.json"


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée de l'application. Retourne le code de sortie."""
    args = _parse_args(argv)
    console.title("Document Power BI", f"v{__version__}")

    try:
        exchange = read(args.input)
        config = load_config(args.config)
    except (ExchangeError, FileNotFoundError, ValueError) as e:
        console.error(str(e))
        return 1

    project_dir = os.path.dirname(exchange.source)
    inputs = _remembered_inputs(exchange, config, project_dir)

    console.blank()
    console.field("Rapport", exchange.report.name)
    console.field("Captures", str(sum(len(shots) for shots in exchange.captures.values())))
    console.field("Plan", config.path)

    console.step("Écriture du document")
    output_dir = args.output or os.path.join(
        project_dir, output_directory(exchange, config, inputs)
    )

    try:
        result = write_document(exchange, config, inputs, output_dir)
    except DocumentError as e:
        console.blank()
        console.banner("Document abandonné", ok=False)
        console.error(str(e))
        return 1

    report_result(result)
    if not args.keep:
        discard(args.input)

    console.blank()
    console.banner("Documentation générée")
    console.field("Fichier", result.path)
    return 0


def _remembered_inputs(exchange, config, project_dir: str) -> dict:
    """
    Réponses de la dernière génération, ou les valeurs du plan.

    Cette application ne dialogue pas : c'est le pipeline qui pose les
    questions. Lancée seule, elle reprend ce que le fichier de réponses garde —
    exactement ce dont on a besoin pour réessayer un plan sans tout resaisir.
    """
    context = base_context(exchange.report, config)
    path = answers.path(config, {"report": exchange.report}, project_dir)
    return default_inputs(config, context, answers.read(path))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.apps.document",
        description="Écrit la documentation Word à partir du fichier d'échange.",
    )
    parser.add_argument(
        "-i", "--input", default=INPUT_NAME, help=f"Fichier d'échange lu (défaut : {INPUT_NAME})"
    )
    parser.add_argument(
        "-o", "--output", default="", help="Dossier du document (défaut : celui du plan)"
    )
    parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_PATH, help="Plan du document (YAML)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="Ne pas supprimer le fichier d'échange consommé"
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
