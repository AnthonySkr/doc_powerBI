"""
Ce qu'on attend de celui qui prend les captures.

Un enregistreur sait quatre choses, et rien d'autre :

    montrer une page        et dire où son canevas est rendu à l'écran
    appliquer un signet     en cliquant son bouton
    prendre une région      et en retourner un PNG
    se refermer

Tout le reste — quoi capturer, où le ranger, comment recadrer — vit au-dessus,
dans du code qui ne dépend ni de Power BI ni d'un écran. C'est ce qui permet
d'éprouver la chaîne entière avec `fake.FakeRecorder`, sans Windows et sans
Power BI installé, puis de ne plus avoir à mettre en doute que le pilotage
lui-même (`desktop.DesktopRecorder`).
"""

from typing import Protocol, runtime_checkable

from src.gui_automator.geometry import Rect
from src.gui_automator.plan import PagePlan

__all__ = ["CaptureError", "Recorder"]


class CaptureError(Exception):
    """
    La capture n'a pas pu se faire.

    Porteuse d'un message rédigé pour l'utilisateur : Power BI fermé, fenêtre
    introuvable, outil absent. Aucune de ces situations n'est un bogue — ce
    sont des conditions d'exécution, et elles se lisent dans la console.
    """


@runtime_checkable
class Recorder(Protocol):
    """Pilote de capture. Voir `desktop` pour le vrai, `fake` pour l'autre."""

    def start(self) -> None:
        """Se met en état de capturer. Lève `CaptureError` s'il ne peut pas."""

    def show_page(self, page: PagePlan) -> Rect:
        """
        Affiche la page et retourne le rectangle **écran** où son canevas est
        rendu, en pixels.

        C'est le seul point où le monde réel entre dans le calcul : tout le
        recadrage en découle (voir `geometry.place`).
        """
        ...

    def grab(self, area: Rect) -> bytes:
        """Capture une région de l'écran et la retourne en PNG."""
        ...

    def measure(self, page: PagePlan, keep: Rect | None = None) -> Rect:
        """
        Où le canevas de la page affichée est rendu **maintenant**, sans en changer.

        Un signet peut ouvrir ou replier le volet Filtres : le canevas se
        redimensionne, et tout cadrage calculé avant tombe à côté. `keep` est
        la mesure d'avant, que l'enregistreur peut garder s'il doute.
        """
        ...

    def apply_bookmark(self, title: str, trigger: Rect, rendered: Rect, undo: bool = False) -> bool:
        """
        Applique un signet de la page affichée, et dit s'il l'a été.

        `trigger` est la zone **écran** du bouton qui y mène, vide si aucun
        n'y mène ; `rendered`, celle du canevas, où l'effet doit se voir.
        `undo` : le signet défait un autre — il doit changer l'affichage.
        """
        ...

    def stop(self) -> None:
        """Rend la main. Appelé quoi qu'il arrive, y compris après une erreur."""
