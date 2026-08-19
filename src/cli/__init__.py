"""Interface en ligne de commande."""

import sys

from src import console
from src.cli.arguments import parse_args
from src.pipeline import PipelineError, run

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du script. Retourne le code de sortie."""
    try:
        output_dir = run(parse_args(argv))
    except PipelineError as e:
        console.warn(str(e))
        return 1
    except KeyboardInterrupt:
        console.blank()
        console.warn("Génération interrompue")
        return 130

    console.blank()
    console.banner(f"Terminé — Sortie dans : {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
