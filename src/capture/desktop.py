"""
Capture depuis Power BI Desktop (Windows).

Pourquoi ces outils-là
──────────────────────
Power BI Desktop ne rend pas ses visuels comme des contrôles Windows : le
canevas est une surface dessinée d'un bloc, dont l'automatisation ne sait rien
extraire. Il n'existe donc pas d'API qui donne « l'image du visuel X » — ni
dans Desktop, ni dans les outils externes. Ce qu'on peut faire, en revanche,
c'est photographier l'écran et **recadrer d'après le rapport**, qui déclare la
place de chaque visuel au pixel logique près (voir `geometry`).

D'où deux outils, chacun sur un seul travail :

    pywinauto   trouver la fenêtre, l'amener devant, changer de page
    mss         photographier une région de l'écran, et la rendre en PNG

Les deux sont en option (`pip install -e ".[capture]"`) : un poste qui ne
documente pas de captures n'a pas à les installer, et le document reste
complet sans elles — avec ses emplacements réservés, comme avant.

    Écartés : `pbi-tools` et les API du service, qui n'exportent qu'un rapport
    entier ; Playwright, qui ne voit que Power BI **Service**, pas Desktop ;
    AutoHotkey, qui obligerait l'utilisateur à installer un second exécutable.

Ce que ce module suppose
────────────────────────
Que le rapport soit **déjà ouvert** dans Power BI Desktop, affiché en mode
Rapport. C'est volontaire : ouvrir le `.pbip` soi-même, c'est attendre un
chargement de durée inconnue, parfois une demande d'identifiants — autant de
choses qui échouent silencieusement. Laisser l'utilisateur ouvrir son rapport
comme il en a l'habitude est plus sûr, et rend la mise au point possible.

Le cadrage du canevas dans la fenêtre est **déclaré**, pas deviné : le ruban,
les volets de droite et la barre d'onglets ont des tailles qui dépendent de la
version et de l'écran. Ils se règlent dans `capture.window` du plan, et se
vérifient avec `python -m src.capture --calibrate`, qui écrit ce qu'il croit
être le canevas pour qu'on le regarde.
"""

from dataclasses import dataclass, field

from src import console
from src.capture.geometry import Rect
from src.capture.plan import PagePlan
from src.capture.recorder import CaptureError

__all__ = ["DesktopOptions", "DesktopRecorder", "Insets"]

_MISSING = (
    "Capture indisponible : `pywinauto` et `mss` ne sont pas installés. "
    'Installez-les avec `pip install -e ".[capture]"`.'
)


@dataclass(frozen=True)
class Insets:
    """
    Ce qui entoure le canevas dans la fenêtre, en pixels.

    Le ruban en haut, les volets Visualisations et Filtres à droite, la barre
    des onglets de page en bas. Ces tailles dépendent de la version de Power BI
    et de la résolution : elles se règlent plutôt qu'elles ne se devinent.
    """

    left: int = 0
    top: int = 130
    right: int = 340
    bottom: int = 60


@dataclass(frozen=True)
class DesktopOptions:
    """Réglages du pilotage, tels que `capture:` les déclare dans le plan."""

    # Fragment cherché dans le titre de la fenêtre. Power BI Desktop intitule
    # la sienne « <rapport> - Power BI Desktop ».
    window_title: str = "Power BI Desktop"
    insets: Insets = field(default_factory=Insets)
    # Temps laissé au rendu après un changement de page, en secondes. Un
    # visuel capturé trop tôt montre son squelette de chargement.
    settle_seconds: float = 1.5
    # Changer de page à la main plutôt que par automatisation : le script
    # s'arrête et attend. Plus lent, mais jamais pris en défaut — c'est le mode
    # à employer pour éprouver le reste de la chaîne.
    manual_pages: bool = False

    @classmethod
    def from_plan(cls, capture: dict) -> DesktopOptions:
        """Réglages déclarés dans la section `capture:` du plan."""
        window = capture.get("window") or {}
        return cls(
            window_title=str(window.get("title") or cls.window_title),
            insets=Insets(
                left=int(window.get("inset_left", Insets.left)),
                top=int(window.get("inset_top", Insets.top)),
                right=int(window.get("inset_right", Insets.right)),
                bottom=int(window.get("inset_bottom", Insets.bottom)),
            ),
            settle_seconds=float(capture.get("settle_seconds", cls.settle_seconds)),
            manual_pages=bool(capture.get("manual_pages", cls.manual_pages)),
        )


class DesktopRecorder:
    """Pilote Power BI Desktop et photographie son canevas."""

    def __init__(self, options: DesktopOptions | None = None):
        self.options = options or DesktopOptions()
        self._window = None
        self._screen = None

    # ── Cycle de vie ──────────────────────────────────────────────
    def start(self) -> None:
        """Trouve la fenêtre de Power BI Desktop et l'amène devant."""
        pywinauto, mss = _import_tools()
        _claim_real_pixels()

        try:
            desktop = pywinauto.Desktop(backend="uia")
            self._window = desktop.window(title_re=f".*{self.options.window_title}.*")
            self._window.wait("exists ready", timeout=10)
        except Exception as e:
            raise CaptureError(
                f"Fenêtre Power BI Desktop introuvable ({e}). "
                "Ouvrez le rapport dans Power BI Desktop, puis relancez."
            ) from e

        self._window.set_focus()
        self._screen = mss.mss()
        console.done(f"fenêtre trouvée : {self._window.window_text()}")

    def stop(self) -> None:
        """Referme la capture d'écran. Power BI reste ouvert : il l'était déjà."""
        if self._screen is not None:
            self._screen.close()
            self._screen = None
        self._window = None

    # ── Capture ───────────────────────────────────────────────────
    def show_page(self, page: PagePlan) -> Rect:
        """Affiche la page demandée et retourne la zone de canevas à l'écran."""
        if self.options.manual_pages:
            _ask_for_page(page)
        else:
            self._select_page(page)

        _settle(self.options.settle_seconds)
        return self.viewport()

    def viewport(self) -> Rect:
        """
        Zone de la fenêtre où le canevas est rendu, marges déclarées déduites.

        `geometry.fit` s'occupe ensuite d'y placer le canevas : c'est lui qui
        tient compte du fait que Power BI le centre en conservant ses
        proportions, d'où les bandes vides sur les côtés.
        """
        window = self._require_window()
        insets = self.options.insets
        box = window.rectangle()
        frame = Rect(box.left, box.top, box.right - box.left, box.bottom - box.top)
        return frame.inset(insets.left, insets.top, insets.right, insets.bottom)

    def window_frame(self) -> Rect:
        """Fenêtre entière — ce que `--calibrate` capture pour comparaison."""
        box = self._require_window().rectangle()
        return Rect(box.left, box.top, box.right - box.left, box.bottom - box.top)

    def grab(self, area: Rect) -> bytes:
        """Photographie une région de l'écran et la retourne en PNG."""
        if self._screen is None:
            raise CaptureError("Capture non démarrée : appelez `start()` d'abord.")

        _, mss = _import_tools()
        region = {
            "left": int(area.left),
            "top": int(area.top),
            "width": int(area.width),
            "height": int(area.height),
        }
        try:
            shot = self._screen.grab(region)
        except Exception as e:
            raise CaptureError(f"Région {region} non capturable ({e})") from e
        return mss.tools.to_png(shot.rgb, shot.size)

    # ── Pages ─────────────────────────────────────────────────────
    def _select_page(self, page: PagePlan) -> None:
        """
        Clique l'onglet de la page, en bas de la fenêtre.

        L'onglet porte le nom affiché de la page. Introuvable, le script ne
        s'arrête pas : il capture ce qui est à l'écran et le signale. Une page
        manquée se rattrape en relançant sur elle seule, ou en `manual_pages`.
        """
        window = self._require_window()
        try:
            tab = window.child_window(title=page.title, control_type="TabItem")
            tab.wait("exists ready", timeout=5)
            tab.click_input()
        except Exception as e:  # noqa: BLE001
            # L'automatisation d'interface échoue de mille façons selon la
            # version : aucune ne vaut d'abandonner la séance.
            console.warn(f"Onglet « {page.title} » non atteint ({e}) — page affichée telle quelle")

    def _require_window(self):
        if self._window is None:
            raise CaptureError("Capture non démarrée : appelez `start()` d'abord.")
        return self._window


def _ask_for_page(page: PagePlan) -> None:
    console.question(f"Affichez la page « {page.title} » dans Power BI Desktop")
    console.note("Puis revenez ici et validez pour lancer la capture.")
    console.ask("Entrée quand la page est à l'écran")


def _settle(seconds: float) -> None:
    """Laisse à Power BI le temps de finir son rendu."""
    if seconds > 0:
        import time  # noqa: PLC0415 — hors de la chaîne d'import du script

        time.sleep(seconds)


def _import_tools():
    """Charge les outils de capture, ou dit lesquels manquent."""
    try:
        import mss  # noqa: PLC0415
        import mss.tools  # noqa: PLC0415
        import pywinauto  # noqa: PLC0415
    except ImportError as e:
        raise CaptureError(_MISSING) from e
    return pywinauto, mss


def _claim_real_pixels() -> None:
    """
    Demande à Windows des coordonnées en vrais pixels.

    Sans cela, un écran agrandi (125 %, 150 %) renvoie au script des
    coordonnées de fenêtre mises à l'échelle, alors que la capture d'écran,
    elle, travaille en pixels réels : le recadrage tomberait à côté, d'autant
    plus loin qu'on s'éloigne du coin supérieur gauche.
    """
    try:
        import ctypes  # noqa: PLC0415

        # PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001
        # Hors Windows, ou déjà réglé par l'hôte : sans conséquence tant que
        # l'affichage est à 100 %.
        console.detail(f"Mise à l'échelle de l'écran non interrogée ({e})")
