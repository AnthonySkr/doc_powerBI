"""Arguments de la ligne de commande."""

import argparse
from dataclasses import dataclass

from src.cli import menu
from src.config import DEFAULT_CONFIG_PATH


@dataclass
class Options:
    pbip_path: str
    config_path: str
    interactive: bool
    pause: bool
    readme: bool = False


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
    parser.add_argument(
        "--mode-emploi",
        "--readme",
        dest="readme",
        action="store_true",
        help="Affiche le mode d'emploi dans le terminal, et rien d'autre",
    )
    args = parser.parse_args(argv)

    if args.readme:
        # Rien à documenter : la question du rapport n'a pas lieu d'être.
        return Options(
            pbip_path="",
            config_path=args.config,
            interactive=not args.no_input,
            pause=not args.no_pause,
            readme=True,
        )

    return Options(
        pbip_path=_pbip(args).strip().strip('"').strip("'"),
        config_path=args.config,
        interactive=not args.no_input,
        pause=not args.no_pause,
    )


def _pbip(args) -> str:
    """
    Le rapport à documenter.

    Nommé sur la ligne de commande — un glisser-déposer sur l'exécutable le
    fait — il est pris tel quel. Sinon l'application s'ouvre sur son menu
    d'accueil, d'où l'utilisateur peut aussi lire le mode d'emploi avant de
    se lancer.

    `--no-input` demande qu'aucune question ne soit posée : sans rapport à
    documenter il n'y a rien à faire, et le pipeline le dira plus clairement
    qu'un menu qui s'afficherait dans le vide.
    """
    if args.pbip:
        return args.pbip
    if args.no_input:
        return ""
    return menu.choose()
