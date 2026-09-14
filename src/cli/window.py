"""
Fenêtre console de l'exécutable distribué.

Ouvert par double-clic ou par glisser-déposer, le .exe obtient une console qui
se referme dès la fin du programme : sans une attente explicite, le compte rendu
et les messages d'erreur disparaissent avant d'avoir été lus.

Deux sorties à couvrir, donc :

    fin normale ou erreur prévue  ->  `close`, appelé par le point d'entrée
    plantage imprévu              ->  `install_crash_handler`, via `sys.excepthook`

Le second cas n'est *pas* un `except Exception` au milieu du programme : une
erreur qu'on ne sait pas traiter n'a pas à être avalée. Elle remonte jusqu'au
bout, Python la confie au gestionnaire posé ici, qui l'affiche en entier et
retient la fenêtre le temps de la lire.

`--no-pause` désactive l'attente pour une exécution automatisée.
"""

import sys
import traceback
from contextlib import suppress
from types import TracebackType

from src import console, paths


class ConsoleWindow:
    """
    Décide si la fenêtre doit être retenue, et la retient le cas échéant.

    `pause` reste modifiable : le point d'entrée le rabat sur `False` lorsque
    `--no-pause` est passé, ce qu'il ne sait qu'après lecture des arguments.
    """

    def __init__(self):
        # En développement, la console appartient à l'utilisateur : elle ne se
        # referme pas toute seule et il n'y a rien à retenir.
        self.pause = paths.is_frozen()

    def install_crash_handler(self) -> None:
        """Confie les erreurs non traitées à `report_crash`."""
        sys.excepthook = self.report_crash

    def report_crash(
        self,
        kind: type[BaseException],
        error: BaseException,
        trace: TracebackType | None,
    ) -> None:
        """Affiche une erreur imprévue en entier, puis retient la fenêtre."""
        console.blank()
        console.banner("Erreur inattendue", ok=False)
        console.error("Détail ci-dessous — joignez-le à votre demande d'aide :")
        traceback.print_exception(kind, error, trace)
        self.wait()

    def wait(self) -> None:
        """Attend une touche avant de rendre la main."""
        if not self.pause:
            return

        console.blank()
        # Entrée fermée (EOFError), inaccessible (OSError) ou absente —
        # `input(): lost sys.stdin`, un RuntimeError. Une tâche planifiée n'a
        # personne pour appuyer sur Entrée : ne pas bloquer.
        with suppress(EOFError, OSError, RuntimeError):
            console.ask("Entrée pour fermer cette fenêtre")

    def close(self, code: int) -> int:
        """Retient la fenêtre, puis retourne le code de sortie du script."""
        self.wait()
        return code
