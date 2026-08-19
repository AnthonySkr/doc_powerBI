"""Interface en ligne de commande."""

import os
import sys
import traceback

from src import console
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
    """Laisse la fenêtre ouverte avant de rendre la main, si elle allait se fermer."""
    if getattr(options, "pause", True) and _console_will_close():
        console.blank()
        try:
            input("Appuyez sur Entrée pour fermer cette fenêtre… ")
        except (EOFError, KeyboardInterrupt):
            pass
    return code


def _console_will_close() -> bool:
    """
    Vrai si la fenêtre console disparaîtra à la fin du programme.

    C'est le cas d'un double-clic ou d'un glisser-déposer sur l'exécutable :
    Windows ouvre une console pour lui seul et la referme aussitôt après —
    résultats et messages d'erreur compris. Lancé depuis un terminal déjà
    ouvert, le programme doit au contraire rendre la main sans rien demander.
    """
    if os.name != "nt":
        return False

    # Entrée redirigée ou absente (tâche planifiée, script) : s'arrêter
    # bloquerait indéfiniment.
    if sys.stdin is None or not sys.stdin.isatty():
        return False

    try:
        import ctypes

        # GetConsoleProcessList retourne le nombre de processus attachés à la
        # console. Un seul — le nôtre — signifie qu'elle a été ouverte pour
        # lui et se fermera avec lui.
        buffer = (ctypes.c_uint * 2)()
        return ctypes.windll.kernel32.GetConsoleProcessList(buffer, 2) <= 1
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    sys.exit(main())
