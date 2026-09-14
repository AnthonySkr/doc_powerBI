"""
Point d'entrée en ligne de commande.

    arguments.py   options de la ligne de commande
    window.py      fenêtre console de l'exécutable : attente et plantages
    prompts.py     questionnaire déclaré par `inputs:`
    questions.py   questions élémentaires posées au terminal
    editing.py     réécriture des textes types du plan
    answers.py     mémoire des réponses d'une génération à l'autre

Ce module ne fait que traduire l'issue de la génération en code de sortie ; le
travail lui-même est enchaîné par `src.pipeline`.
"""

import sys

from src import __version__, console
from src.cli.arguments import parse_args
from src.cli.window import ConsoleWindow
from src.pipeline import PipelineError, run

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du script. Retourne le code de sortie."""
    # Posé avant tout : une erreur survenue dès la lecture des arguments doit
    # elle aussi rester lisible.
    window = ConsoleWindow()
    window.install_crash_handler()

    console.title("Documentation Power BI", f"v{__version__}")

    options = parse_args(argv)
    window.pause = window.pause and options.pause

    try:
        output_dir = run(options)
    except PipelineError as e:
        console.blank()
        console.banner("Génération abandonnée", ok=False)
        console.error(str(e))
        return window.close(1)
    except KeyboardInterrupt:
        console.blank()
        console.banner("Génération interrompue", ok=False)
        return window.close(130)

    console.blank()
    console.banner("Documentation générée")
    console.field("Dossier", output_dir)
    return window.close(0)


if __name__ == "__main__":
    sys.exit(main())
