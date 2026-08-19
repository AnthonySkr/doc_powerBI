"""
Affichage console du script.

Tous les messages passent par ce module : le reste du code n'appelle jamais
`print` directement, ce qui laisse un seul endroit à modifier pour changer la
présentation.
"""

from contextlib import contextmanager

WIDTH = 65

_enabled = True


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
    if _enabled:
        print(line)


def banner(text: str) -> None:
    """Titre encadré, pour les grandes étapes du script."""
    _write("=" * WIDTH)
    _write(f"  {text}")
    _write("=" * WIDTH)


def step(text: str) -> None:
    """Titre d'étape."""
    _write("─" * WIDTH)
    _write(f"  {text}")
    _write("─" * WIDTH)


def rule() -> None:
    _write("─" * WIDTH)


def info(message: str) -> None:
    _write(f"  {message}")


def detail(message: str) -> None:
    """Information secondaire, en retrait."""
    _write(f"    {message}")


def warn(message: str) -> None:
    """Anomalie non bloquante : le script continue."""
    _write(f"  ! {message}")


def blank() -> None:
    _write()
