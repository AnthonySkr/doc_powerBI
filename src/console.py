"""
Affichage console du script.

Tous les messages passent par ce module : le reste du code n'appelle jamais
`print` directement, ce qui laisse un seul endroit à modifier pour changer la
présentation (ou rediriger la sortie vers un journal).
"""

WIDTH = 65


def banner(text: str) -> None:
    """Titre encadré, pour les grandes étapes du script."""
    print("=" * WIDTH)
    print(f"  {text}")
    print("=" * WIDTH)


def step(text: str) -> None:
    """Titre d'étape."""
    print("─" * WIDTH)
    print(f"  {text}")
    print("─" * WIDTH)


def rule() -> None:
    print("─" * WIDTH)


def info(message: str) -> None:
    print(f"  {message}")


def detail(message: str) -> None:
    """Information secondaire, en retrait."""
    print(f"    {message}")


def warn(message: str) -> None:
    """Anomalie non bloquante : le script continue."""
    print(f"  ! {message}")


def blank() -> None:
    print()
