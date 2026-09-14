"""
L'application « extraction », à lancer seule.

    python -m src.apps.extract rapport.pbip
    python -m src.apps.extract rapport.pbip -o /tmp/rapport.json

Elle n'écrit qu'un fichier JSON. C'est ce qui la rend éprouvable seule : on
l'ouvre, on regarde ce que le rapport contient vraiment, et on peut le
retoucher pour éprouver l'étape suivante sans rejouer celle-ci.
"""

import argparse
import os
import sys

from src import __version__
from src.apps.extract.collect import ExtractError, collect, open_project
from src.shared import console
from src.shared.exchange import DEFAULT_DIRECTORY, write

# Nom du fichier produit. Le rang en tête dit sa place dans la chaîne.
OUTPUT_NAME = "1-rapport.json"


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée de l'application. Retourne le code de sortie."""
    args = _parse_args(argv)
    console.title("Extraction Power BI", f"v{__version__}")

    try:
        project = open_project(args.pbip)
    except ExtractError as e:
        console.error(str(e))
        return 1

    console.blank()
    console.field("Rapport", project.name)
    console.field("Modèle", os.path.basename(project.semantic_model_dir))  # type: ignore[arg-type]
    console.field("Pages", os.path.basename(project.report_dir))  # type: ignore[arg-type]

    console.step("Lecture du projet")
    exchange = collect(project)

    path = args.output or os.path.join(project.directory, DEFAULT_DIRECTORY, OUTPUT_NAME)
    write(exchange, path)

    console.blank()
    console.banner("Rapport extrait")
    console.field("Fichier", path)
    console.field("Pages", str(len(exchange.report.pages)))
    console.field("Mesures", str(len(exchange.report.all_measures)))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.apps.extract",
        description="Lit un projet Power BI (.pbip) et écrit le fichier d'échange.",
    )
    parser.add_argument("pbip", help="Chemin vers le fichier .pbip")
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help=f"Fichier à écrire (défaut : {DEFAULT_DIRECTORY}/{OUTPUT_NAME} du projet)",
    )
    args = parser.parse_args(argv)
    args.pbip = args.pbip.strip().strip('"').strip("'")
    return args


if __name__ == "__main__":
    sys.exit(main())
