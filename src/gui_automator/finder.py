"""
Trouver la fenêtre de Power BI Desktop parmi celles du bureau.

Pourquoi un module pour ça
──────────────────────────
Chercher « Power BI Desktop » dans le titre ne tient pas. Le titre de la
fenêtre dépend de la version et de ce qui est ouvert :

    Ventes 2024 - Power BI Desktop      les versions anciennes
    Ventes 2024 - Power BI              certaines versions intermédiaires
    Ventes 2024                         les versions récentes — le rapport seul

Un rapport ouvert passait alors pour fermé, et la séance s'arrêtait là.

Ce qui ne change pas, c'est le **processus** qui porte la fenêtre :
`PBIDesktop.exe`, ou `PBIDesktopStore.exe` pour la version du Microsoft Store.
C'est donc lui qu'on cherche. Le titre ne sert plus qu'à départager plusieurs
rapports ouverts en même temps — et seulement si le plan en déclare un.

L'énumération tient dans quelques appels de `user32` et `kernel32`, faits en
`ctypes` : rien à installer de plus que ce que la capture demande déjà. Le
choix de la fenêtre, lui, est du calcul pur (`choose`) — vérifiable hors de
Windows, et c'est ce que font les tests.
"""

import ctypes
from dataclasses import dataclass
from functools import cache
from pathlib import PureWindowsPath

from src.gui_automator.recorder import CaptureError

__all__ = [
    "WindowInfo",
    "choose",
    "claim_real_pixels",
    "locate",
    "maximize",
    "mentions",
    "restore",
    "visible_windows",
]

# Les exécutables de Power BI Desktop partagent tous ce préfixe :
# `PBIDesktop.exe` pour l'installation classique, `PBIDesktopStore.exe` pour la
# version distribuée par le Microsoft Store. Le préfixe plutôt que la liste :
# une variante de plus n'est pas une raison de ne plus reconnaître la fenêtre.
PBI_PROCESS = "pbidesktop"

# Titres qui ne désignent aucun rapport en particulier — ce sont les valeurs
# héritées de l'ancien réglage `capture.window.title`. Les prendre pour
# critère écarterait justement les fenêtres qui ne portent que le nom du
# rapport, c'est-à-dire celles des versions récentes.
GENERIC_TITLES = ("power bi desktop", "power bi")

# Nombre de fenêtres citées dans le message d'erreur : de quoi reconnaître la
# sienne sans noyer la console.
_LISTED = 8

_MAX_PATH = 32768
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SW_RESTORE = 9
_SW_MAXIMIZE = 3

# Dire à Windows que le script travaille en vrais pixels, du plus précis au
# plus ancien : contexte par écran (Windows 10 1703 et au-delà), conscience
# par écran, puis conscience tout court.
_PER_MONITOR_AWARE_V2 = -4
_PROCESS_PER_MONITOR_DPI_AWARE = 2


@dataclass(frozen=True)
class WindowInfo:
    """Une fenêtre de premier plan, telle que Windows la décrit."""

    handle: int
    title: str = ""
    # Nom de l'exécutable qui porte la fenêtre, vide s'il n'a pas pu être lu —
    # le cas d'un Power BI lancé en administrateur, script non élevé.
    process: str = ""
    width: int = 0
    height: int = 0

    @property
    def is_power_bi(self) -> bool:
        """
        Fenêtre de Power BI Desktop ?

        Par le processus, et à défaut — processus illisible — par le suffixe
        que les anciennes versions donnent à leur titre.
        """
        if self.process.lower().startswith(PBI_PROCESS):
            return True
        return not self.process and _has_generic_suffix(self.title)

    @property
    def area(self) -> int:
        """Surface en pixels : ce qui distingue le rapport d'un écran d'accueil."""
        return max(self.width, 0) * max(self.height, 0)

    def describe(self) -> str:
        """Comment la fenêtre s'écrit dans un message destiné à l'utilisateur."""
        title = self.title or "(sans titre)"
        return f"« {title} »{f' [{self.process}]' if self.process else ''}"


# ─────────────────────────────────────────────────────────────
#  Choisir — du calcul pur, vérifiable hors de Windows
# ─────────────────────────────────────────────────────────────


def choose(windows: list[WindowInfo], hint: str = "") -> WindowInfo | None:
    """
    La fenêtre du rapport parmi celles du bureau, ou `None`.

    D'abord les fenêtres de Power BI ; à défaut celles dont le titre porte le
    fragment déclaré par le plan — un poste dont le processus n'est pas lisible
    garde ainsi un recours. Entre plusieurs, on retient celle qui répond au
    fragment, puis la plus grande : la fenêtre d'un rapport est plus large que
    l'écran de démarrage ou qu'une boîte de dialogue.
    """
    pool = [window for window in windows if window.is_power_bi]
    if not pool:
        pool = [window for window in windows if mentions(window.title, hint)]
    if not pool:
        return None
    return max(pool, key=lambda w: (mentions(w.title, hint), bool(w.title), w.area))


def mentions(title: str, hint: str) -> bool:
    """Le titre répond-il au fragment déclaré ? Un fragment générique, non."""
    return _is_specific(hint) and hint.strip().lower() in title.lower()


def _is_specific(hint: str) -> bool:
    """Un fragment qui désigne un rapport, et non « Power BI Desktop »."""
    wanted = hint.strip().lower()
    return bool(wanted) and wanted not in GENERIC_TITLES


def _has_generic_suffix(title: str) -> bool:
    return any(f" - {generic}" in title.lower() for generic in GENERIC_TITLES)


# ─────────────────────────────────────────────────────────────
#  Chercher — l'appel à Windows
# ─────────────────────────────────────────────────────────────


def locate(hint: str = "") -> WindowInfo:
    """
    La fenêtre de Power BI Desktop, ou une erreur qui dit ce qui a été vu.

    Le message d'erreur énumère les fenêtres ouvertes : c'est ce qui permet de
    comprendre, sans outil, pourquoi le rapport n'a pas été reconnu.
    """
    windows = visible_windows()
    found = choose(windows, hint)
    if found is None:
        raise CaptureError(_nothing_found(windows, hint))
    return found


def _nothing_found(windows: list[WindowInfo], hint: str) -> str:
    lines = [
        "Fenêtre Power BI Desktop introuvable.",
        "Ouvrez le rapport dans Power BI Desktop, en mode Rapport, puis relancez.",
    ]
    if _is_specific(hint):
        lines.append(f"Titre cherché : « {hint} » (`capture.window.title` du plan).")
    named = [window.describe() for window in windows if window.title][:_LISTED]
    if named:
        lines.append("Fenêtres vues : " + ", ".join(named) + ".")
    return " ".join(lines)


def visible_windows() -> list[WindowInfo]:
    """Les fenêtres de premier plan visibles. Hors de Windows, aucune."""
    api = _api()
    if api is None:
        return []

    found: list[WindowInfo] = []

    @api.enumproc
    def visit(handle, _lparam):
        if api.user32.IsWindowVisible(handle):
            found.append(_describe(api, handle))
        return True

    api.user32.EnumWindows(visit, 0)
    return found


def restore(handle: int) -> None:
    """
    Sort la fenêtre de la barre des tâches si elle y est réduite.

    Une fenêtre réduite garde des coordonnées, mais rien de ce qu'on
    photographierait : sans cela, la séance produirait des images du bureau.
    """
    api = _api()
    if api is not None and api.user32.IsIconic(handle):
        api.user32.ShowWindow(handle, _SW_RESTORE)


def maximize(handle: int) -> None:
    """
    Agrandit la fenêtre à tout l'écran qui la porte.

    Deux raisons, et la seconde compte autant que la première : une fenêtre
    agrandie donne au canevas la plus grande surface possible, donc des
    captures nettes ; et elle est reproductible, là où une fenêtre posée à la
    main change de taille — donc de cadrage — d'une séance à l'autre.
    """
    api = _api()
    if api is not None:
        api.user32.ShowWindow(handle, _SW_MAXIMIZE)


def claim_real_pixels() -> str:
    """
    Demande à Windows des coordonnées en vrais pixels, et dit ce qu'il a fallu.

    Sans cela, un écran agrandi (125 %, 150 %) renvoie au script des
    coordonnées de fenêtre mises à l'échelle, alors que la capture d'écran,
    elle, travaille en pixels réels : le recadrage tomberait à côté, d'autant
    plus loin qu'on s'éloigne du coin supérieur gauche.

    **À appeler avant toute autre chose** : la conscience d'échelle d'un
    processus se fige dès qu'elle est posée une fois, et `pywinauto` la pose
    lui-même — moins finement — au moment de son import.
    """
    for claim, description in (
        (_claim_per_monitor_v2, "par écran (v2)"),
        (_claim_per_monitor, "par écran"),
        (_claim_system, "à l'échelle du système"),
    ):
        if claim():
            return description
    return "non réglée"


def _claim_per_monitor_v2() -> bool:
    """Windows 10 1703 et au-delà : l'échelle de l'écran qui porte la fenêtre."""
    try:
        context = ctypes.c_void_p(_PER_MONITOR_AWARE_V2)
        return bool(ctypes.windll.user32.SetProcessDpiAwarenessContext(context))  # type: ignore[attr-defined]
    except AttributeError, OSError:
        return False


def _claim_per_monitor() -> bool:
    """Windows 8.1 : même idée, sans le rattrapage des fenêtres déjà ouvertes."""
    try:
        return (
            ctypes.windll.shcore.SetProcessDpiAwareness(  # type: ignore[attr-defined]
                _PROCESS_PER_MONITOR_DPI_AWARE
            )
            == 0
        )
    except AttributeError, OSError:
        return False


def _claim_system() -> bool:
    """Le plus ancien : une seule échelle pour tous les écrans."""
    try:
        return bool(ctypes.windll.user32.SetProcessDPIAware())  # type: ignore[attr-defined]
    except AttributeError, OSError:
        return False


def _describe(api: _Api, handle: int) -> WindowInfo:
    box = api.wintypes.RECT()
    api.user32.GetWindowRect(handle, ctypes.byref(box))
    return WindowInfo(
        handle=handle,
        title=_title(api, handle),
        process=_process_name(api, handle),
        width=box.right - box.left,
        height=box.bottom - box.top,
    )


def _title(api: _Api, handle: int) -> str:
    length = api.user32.GetWindowTextLengthW(handle)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    api.user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value


def _process_name(api: _Api, handle: int) -> str:
    """Nom de l'exécutable qui porte la fenêtre, vide s'il n'est pas lisible."""
    pid = api.wintypes.DWORD()
    api.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    if not pid.value:
        return ""

    process = api.kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        # Processus protégé, ou plus élevé que le nôtre : le titre prendra le
        # relais. Ce n'est pas une erreur, juste moins d'information.
        return ""
    try:
        size = api.wintypes.DWORD(_MAX_PATH)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not api.kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            return ""
        return PureWindowsPath(buffer.value).name
    finally:
        api.kernel32.CloseHandle(process)


# ─────────────────────────────────────────────────────────────
#  Les appels système, déclarés une fois
# ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Api:
    """Les deux bibliothèques de Windows employées ici, et leurs types."""

    user32: ctypes.CDLL
    kernel32: ctypes.CDLL
    wintypes: object
    enumproc: object


@cache
def _api() -> _Api | None:
    """
    `user32` et `kernel32`, signatures déclarées. `None` hors de Windows.

    Sur un Windows 64 bits, un identifiant de fenêtre ne tient pas dans un
    `int` C : sans ces déclarations, ctypes le tronque et les appels échouent.
    """
    try:
        from ctypes import wintypes  # noqa: PLC0415 — indisponible hors de Windows

        user32 = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        enumproc = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
    except AttributeError, ImportError, OSError, ValueError:
        return None

    _declare(user32, kernel32, wintypes, enumproc)
    return _Api(user32=user32, kernel32=kernel32, wintypes=wintypes, enumproc=enumproc)


def _declare(user32, kernel32, wintypes, enumproc) -> None:
    """Types d'arguments et de retour des appels employés ici."""
    user32.EnumWindows.argtypes = [enumproc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
