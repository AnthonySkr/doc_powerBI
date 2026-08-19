"""Arguments de la ligne de commande."""

import argparse
from dataclasses import dataclass

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

    pbip = args.pbip or input("Chemin vers le fichier .pbip : ")

    return Options(
        pbip_path=pbip.strip().strip('"'),
        config_path=args.config,
        interactive=not args.no_input,
        pause=not args.no_pause,
    )
