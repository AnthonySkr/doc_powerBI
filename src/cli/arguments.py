"""Arguments de la ligne de commande."""

import argparse
from dataclasses import dataclass

from src import console
from src.config import DEFAULT_CONFIG_PATH


@dataclass
class Options:
    pbip_path: str
    config_path: str
    interactive: bool
    pause: bool


def parse_args(argv: list[str] | None = None) -> Options:
    parser = argparse.ArgumentParser(
        description="Génère la documentation Word d'un rapport Power BI (.pbip)."
    )
    parser.add_argument("pbip", nargs="?", help="Chemin vers le fichier .pbip")
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Fichier de configuration YAML (défaut : {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "-y",
        "--no-input",
        action="store_true",
        help="Ne pose aucune question : utilise les valeurs par défaut du YAML",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Ne pas attendre de touche à la fin (exécution automatisée)",
    )
    args = parser.parse_args(argv)

    return Options(
        pbip_path=(args.pbip or _ask_pbip()).strip().strip('"').strip("'"),
        config_path=args.config,
        interactive=not args.no_input,
        pause=not args.no_pause,
    )


def _ask_pbip() -> str:
    """
    Demande le fichier à documenter, faute d'être lancé avec.

    C'est le cas d'un double-clic sur l'exécutable. Le glisser-déposer du
    `.pbip` dans la fenêtre est la voie la plus sûre : il écrit le chemin
    complet, entre guillemets, sans faute de frappe possible.
    """
    console.question("Quel rapport documenter ?")
    console.note("Déposez le fichier .pbip dans cette fenêtre, ou collez son chemin.")
    return console.ask("Fichier .pbip")
