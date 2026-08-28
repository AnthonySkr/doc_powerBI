"""Interface en ligne de commande."""

import sys
import traceback

from src import console, paths
from src.cli.arguments import parse_args
from src.pipeline import PipelineError, run

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du script. Retourne le code de sortie."""
    options = None
    try:
        options = parse_args(argv)
        output_dir = run(options)
    except PipelineError as e:
        console.warn(str(e))
        return _finish(1, options)
    except KeyboardInterrupt:
        console.blank()
        console.warn("Génération interrompue")
        return _finish(130, options)
    except Exception:  # noqa: BLE001
        # Une erreur imprévue ne doit pas disparaître avec la fenêtre : elle
        # est affichée en entier, puis la pause laisse le temps de la lire.
        console.blank()
        console.warn("Erreur inattendue — détail ci-dessous :")
        traceback.print_exc()
        return _finish(1, options)

    console.blank()
    console.banner(f"Terminé — Sortie dans : {output_dir}")
    return _finish(0, options)


def _finish(code: int, options) -> int:
    """
    Attend une touche avant de rendre la main, lorsque le programme tourne
    depuis l'exécutable distribué.

    Ouvert par double-clic ou par glisser-déposer, celui-ci obtient une console
    qui se referme dès la fin du programme : sans cette attente, le compte
    rendu et les messages d'erreur disparaissent avant d'avoir été lus.
    `--no-pause` la désactive pour une exécution automatisée.
    """
    if not paths.is_frozen() or not getattr(options, "pause", True):
        return code

    console.blank()
    try:
        input("Appuyez sur Entrée pour fermer cette fenêtre… ")
    except Exception:  # noqa: BLE001, S110
        # Entrée absente ou fermée (tâche planifiée) : ne pas bloquer.
        pass
    return code


if __name__ == "__main__":
    sys.exit(main())
