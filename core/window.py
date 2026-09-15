"""
Fenêtre console de l'exécutable distribué.
"""

import sys
import traceback
from contextlib import suppress
from types import TracebackType

from core import console, paths


class ConsoleWindow:
    """
    Décide si la fenêtre doit être retenue, et la retient le cas échéant.

    `pause` reste modifiable : le point d'entrée le rabat sur `False` lorsque
    `--no-pause` est passé, ce qu'il ne sait qu'après lecture des arguments.
    """

    def __init__(self):
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
        with suppress(EOFError, OSError, RuntimeError):
            console.ask("Entrée pour fermer cette fenêtre")

    def close(self, code: int) -> int:
        """Retient la fenêtre, puis retourne le code de sortie du script."""
        self.wait()
        return code
