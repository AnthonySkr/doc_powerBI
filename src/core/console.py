"""
Affichage console du script.

Tous les messages passent par ici : le reste du code n'appelle jamais `print`
ni `input`, ce qui laisse un seul endroit où changer la présentation.

Deux précautions, prises une fois pour toutes à l'import, rendent la sortie
lisible aussi bien dans un terminal moderne que dans une vieille console `cmd`
ou dans un fichier : les couleurs ne sont écrites que sur un vrai terminal (et
jamais si `NO_COLOR` est renseigné), et les caractères de dessin se réduisent à
l'ASCII quand l'encodage ne sait pas les porter.
"""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

WIDTH = 66
"""Largeur du dessin, en caractères."""


@dataclass
class _Output:
    """État de la sortie. Un objet plutôt qu'une variable globale mutée."""

    enabled: bool = True


_output = _Output()


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
        # Importé ici plutôt qu'en tête : `ctypes` n'a rien à faire dans la
        # chaîne d'import du script sur les plateformes qui n'en ont pas usage.
        import ctypes  # noqa: PLC0415

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
    """La sortie est-elle un terminal qui accepte les couleurs ?"""
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
    """Caractère de dessin, dans sa forme Unicode ou ASCII selon la console."""
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
def silenced() -> Iterator[None]:
    """Supprime toute sortie le temps du bloc (tests, exécution pilotée)."""
    previous, _output.enabled = _output.enabled, False
    try:
        yield
    finally:
        _output.enabled = previous


def _write(line: str = "") -> None:
    """
    Écrit une ligne, sans jamais faire échouer le script sur un caractère.

    Un nom venu de Power BI peut porter n'importe quoi : perdre un document
    déjà produit sur un `UnicodeEncodeError` d'affichage serait absurde. Les
    caractères qui ne passent pas sont remplacés, et la ligne est écrite.
    """
    if not _output.enabled:
        return
    try:
        print(line)  # noqa: T201 — l'un des deux seuls `print` du projet
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", "") or "ascii"
        print(line.encode(encoding, "replace").decode(encoding, "replace"))  # noqa: T201


def blank() -> None:
    """Ligne vide."""
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
    Titre d'étape, précédé de son rang lorsqu'il est connu.

    Sur un gros rapport, la lecture du modèle prend le temps qu'il faut : mieux
    vaut « 1/3 » qu'une fenêtre muette.
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
    """Message courant, sans marque particulière."""
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

    La valeur proposée s'affiche entre crochets : un Entrée la valide, et
    reconduit ainsi les réponses de la génération précédente.
    """
    suffix = paint(f" [{default}]", "dim") if default else ""
    return _prompt(f"  {label}{suffix} {paint(glyph('arrow'), 'frame')} ")


def note(message: str) -> None:
    """Consigne d'usage affichée sous une question."""
    _write(paint(f"  {message}", "dim"))


def option(number: int, text: str, retained: bool = False) -> None:
    """
    Une entrée numérotée d'une question à choix.

    Celles retenues la dernière fois sont marquées : on les reconduit d'un
    Entrée, plutôt que de les ressaisir de mémoire.
    """
    mark = paint(f"   {glyph('ok')} retenu", "ok") if retained else ""
    _write(f"    {paint(str(number).rjust(3) + '.', 'key')} {text}{mark}")


def question(label: str) -> None:
    """Intitulé d'une question développée sur plusieurs lignes."""
    _write()
    _write("  " + paint(label, "bold"))


def _prompt(text: str) -> str:
    """
    Lit une réponse au terminal.

    L'invite passe par `stdout` plutôt que par l'argument de `input`, qui
    l'écrit sur `stderr` : une sortie redirigée porte ainsi les questions.
    """
    if _output.enabled:
        print(text, end="", flush=True)  # noqa: T201 — l'autre, pour l'invite
    return input()
