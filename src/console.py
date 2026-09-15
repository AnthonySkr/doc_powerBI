"""
Affichage console du script.

Tous les messages passent par ce module : le reste du code n'appelle jamais
`print` ni `input` directement, ce qui laisse un seul endroit à modifier pour
changer la présentation.

La sortie est celle d'une petite application de terminal : un bandeau, des
étapes numérotées, des questions encadrées et un bilan final. Trois choses la
rendent lisible partout où l'exécutable est lancé — un terminal Windows moderne,
une vieille console `cmd`, ou une sortie redirigée vers un fichier :

  - les couleurs ne sont écrites que si la sortie est un vrai terminal, et
    jamais si `NO_COLOR` est renseigné (convention `no-color.org`) ;
  - les caractères de dessin sont remplacés par leurs équivalents ASCII quand
    l'encodage de la console ne sait pas les porter — sans quoi la génération
    s'arrêterait sur un `UnicodeEncodeError`, après tout le travail ;
  - rien de tout cela n'est décidé à chaque ligne : les deux réponses sont
    calculées une fois, à l'import.
"""

import os
import sys
from contextlib import contextmanager

WIDTH = 66

_enabled = True


# ─────────────────────────────────────────────────────────────
#  Capacités du terminal
# ─────────────────────────────────────────────────────────────


def _enable_windows_ansi() -> bool:
    """
    Autorise les séquences de couleur dans une console Windows.

    Les consoles Windows ne les interprètent que si le mode « terminal
    virtuel » est armé. Il l'est d'office dans Windows Terminal, mais pas
    toujours dans la fenêtre ouverte par un double-clic sur l'exécutable :
    sans cela l'utilisateur lirait les codes d'échappement en clair.
    """
    try:
        import ctypes

        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:  # noqa: BLE001
        return False


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        return _enable_windows_ansi()
    return True


def _supports_unicode() -> bool:
    """La console sait-elle écrire les caractères de dessin employés ici ?"""
    encoding = getattr(sys.stdout, "encoding", "") or ""
    try:
        "─│╭╮╰╯✓✗•›»".encode(encoding)
    except LookupError, UnicodeEncodeError, TypeError:
        return False
    return True


_COLOR = _supports_color()
_UNICODE = _supports_unicode()


# ─────────────────────────────────────────────────────────────
#  Palette et caractères de dessin
# ─────────────────────────────────────────────────────────────

# Le dessin se réduit à l'ASCII quand la console ne sait pas porter mieux.
_GLYPHS = {
    "h": ("─", "-"),
    "v": ("│", "|"),
    "tl": ("╭", "+"),
    "tr": ("╮", "+"),
    "bl": ("╰", "+"),
    "br": ("╯", "+"),
    "ok": ("✓", "v"),
    "ko": ("✗", "x"),
    "warn": ("!", "!"),
    "dot": ("•", "-"),
    "arrow": ("›", ">"),
    "step": ("▪", "*"),
}


def glyph(name: str) -> str:
    unicode_form, ascii_form = _GLYPHS[name]
    return unicode_form if _UNICODE else ascii_form


_STYLES = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "frame": "\033[36m",  # cyan — la structure de l'affichage
    "ok": "\033[32m",  # vert — ce qui a abouti
    "warn": "\033[33m",  # jaune — ce qui mérite un regard
    "ko": "\033[31m",  # rouge — ce qui a échoué
    "key": "\033[36m",  # cyan — les libellés d'un tableau clé / valeur
}


def paint(text: str, style: str) -> str:
    """Applique une couleur, ou retourne le texte tel quel si elles sont hors jeu."""
    if not _COLOR or not text:
        return text
    return f"{_STYLES[style]}{text}{_STYLES['reset']}"


# ─────────────────────────────────────────────────────────────
#  Sortie
# ─────────────────────────────────────────────────────────────


@contextmanager
def silenced():
    """Supprime toute sortie le temps du bloc (tests, exécution pilotée)."""
    global _enabled
    previous, _enabled = _enabled, False
    try:
        yield
    finally:
        _enabled = previous


def _write(line: str = "") -> None:
    """
    Écrit une ligne, sans jamais faire échouer le script sur un caractère.

    Le choix des caractères de dessin tient déjà compte de l'encodage de la
    console, mais pas le texte des messages : un nom de mesure venu de Power BI
    peut porter n'importe quoi. Une console incapable de l'écrire ferait
    remonter un `UnicodeEncodeError` — et perdrait un document déjà produit
    pour un caractère d'affichage. Les caractères qui ne passent pas sont donc
    remplacés, et la ligne est écrite quand même.
    """
    if not _enabled:
        return
    try:
        print(line)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", "") or "ascii"
        print(line.encode(encoding, "replace").decode(encoding, "replace"))


def blank() -> None:
    _write()


# ─────────────────────────────────────────────────────────────
#  Structure
# ─────────────────────────────────────────────────────────────


def title(text: str, subtitle: str = "") -> None:
    """Bandeau d'ouverture de l'application."""
    inner = WIDTH - 2
    top = glyph("tl") + glyph("h") * inner + glyph("tr")
    bottom = glyph("bl") + glyph("h") * inner + glyph("br")
    side = glyph("v")

    label = f"  {text.upper()}"
    padding = inner - len(label) - len(subtitle) - 2
    body = f"{label}{' ' * max(padding, 1)}{subtitle}  "

    _write(paint(top, "frame"))
    _write(paint(side, "frame") + paint(body[:inner].ljust(inner), "bold") + paint(side, "frame"))
    _write(paint(bottom, "frame"))


def banner(text: str, ok: bool = True) -> None:
    """Bandeau de clôture : ce que la génération a produit, ou pourquoi elle s'arrête."""
    inner = WIDTH - 2
    mark = glyph("ok") if ok else glyph("ko")
    body = f"  {mark} {text}"[:inner].ljust(inner)

    _write(paint(glyph("tl") + glyph("h") * inner + glyph("tr"), "frame"))
    _write(
        paint(glyph("v"), "frame") + paint(body, "ok" if ok else "ko") + paint(glyph("v"), "frame")
    )
    _write(paint(glyph("bl") + glyph("h") * inner + glyph("br"), "frame"))


def step(text: str, number: int | None = None, total: int | None = None) -> None:
    """
    Titre d'étape.

    Le rang de l'étape est affiché lorsqu'il est connu : sur un rapport
    volumineux, la lecture du modèle prend le temps qu'il faut, et savoir qu'on
    en est à la première étape sur quatre vaut mieux qu'une fenêtre muette.
    """
    counter = f" {number}/{total} " if number and total else " "
    head = f"{glyph('h') * 2}{counter}{glyph('step')} "
    _write()
    _write(
        paint(head, "frame")
        + paint(text, "bold")
        + paint(" " + glyph("h") * _fill(head, text), "frame")
    )


def _fill(head: str, text: str) -> int:
    """Nombre de traits complétant une ligne d'étape jusqu'à la largeur voulue."""
    return max(WIDTH - len(head) - len(text) - 1, 0)


def field(label: str, value: str, width: int = 14) -> None:
    """Ligne d'un tableau clé / valeur — le rapport traité, le plan employé."""
    _write("  " + paint(label.ljust(width), "key") + str(value))


# ─────────────────────────────────────────────────────────────
#  Messages
# ─────────────────────────────────────────────────────────────


def info(message: str) -> None:
    _write(f"  {message}")


def done(message: str) -> None:
    """Étape franchie : ce qui vient d'aboutir."""
    _write("  " + paint(glyph("ok"), "ok") + f" {message}")


def detail(message: str) -> None:
    """Information secondaire, en retrait."""
    _write(paint(f"    {message}", "dim"))


def warn(message: str) -> None:
    """Anomalie non bloquante : le script continue."""
    _write("  " + paint(f"{glyph('warn')} {message}", "warn"))


def error(message: str) -> None:
    """Anomalie bloquante : le script s'arrête."""
    _write("  " + paint(f"{glyph('ko')} {message}", "ko"))


# ─────────────────────────────────────────────────────────────
#  Questions
# ─────────────────────────────────────────────────────────────


def ask(label: str, default: str = "") -> str:
    """
    Pose une question et retourne la réponse brute.

    La valeur proposée est affichée entre crochets : la valider d'un Entrée est
    le geste attendu, et c'est celui qui reconduit à l'identique les réponses de
    la génération précédente.
    """
    suffix = paint(f" [{default}]", "dim") if default else ""
    return _prompt(f"  {label}{suffix} {paint(glyph('arrow'), 'frame')} ")


def note(message: str) -> None:
    """Consigne d'usage affichée sous une question."""
    _write(paint(f"  {message}", "dim"))


def option(number: int, text: str, retained: bool = False) -> None:
    """
    Une entrée numérotée d'une question à choix.

    Les entrées déjà retenues la dernière fois sont marquées : c'est ce qui
    permet de les reconduire d'un Entrée, plutôt que de les ressaisir de
    mémoire — et d'en oublier une.
    """
    mark = paint(f"   {glyph('ok')} retenu", "ok") if retained else ""
    _write(f"    {paint(str(number).rjust(3) + '.', 'key')} {text}{mark}")


def question(label: str) -> None:
    """Intitulé d'une question développée sur plusieurs lignes."""
    _write()
    _write("  " + paint(label, "bold"))


def _prompt(text: str) -> str:
    """
    Lit une réponse.

    L'invite passe par `stdout` plutôt que par l'argument de `input`, qui
    l'écrit sur `stderr` : redirigée, la sortie du script porte ainsi les
    questions posées, et non des réponses sans intitulé.
    """
    if _enabled:
        print(text, end="", flush=True)
    return input()
