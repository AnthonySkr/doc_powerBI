"""
Menu d'accueil, à l'ouverture de l'application.

L'exécutable est distribué à des gens qui n'ouvriront pas forcément le
`README.md` livré à côté. Lancé sans rapport à documenter — un double-clic —
il commence donc par proposer un choix : générer la documentation, ou lire le
mode d'emploi.

Le menu ne s'affiche pas lorsque le rapport est déjà connu : glisser un `.pbip`
sur l'exécutable, ou le passer en argument, reste le chemin le plus court et
n'a pas à traverser une question de plus.
"""

from src import console
from src.cli import guide

__all__ = ["choose"]

GENERER = "1"
MODE_EMPLOI = "2"


def choose() -> str:
    """
    Pose le choix d'accueil, puis retourne le chemin du `.pbip` à documenter.

    Le mode d'emploi ne clôt pas l'application : une fois lu, le menu revient,
    et l'utilisateur enchaîne sur la génération sans avoir à relancer.
    """
    while True:
        console.question("Que souhaitez-vous faire ?")
        console.option(int(GENERER), "Générer la documentation d'un rapport")
        console.option(int(MODE_EMPLOI), "Lire le mode d'emploi")

        answer = console.ask(f"Choix parmi {GENERER}-{MODE_EMPLOI}", GENERER).strip() or GENERER
        if answer == MODE_EMPLOI:
            guide.show()
            continue
        if answer != GENERER:
            console.warn("Répondez par 1 ou 2.")
            continue
        return ask_pbip()


def ask_pbip() -> str:
    """
    Demande le fichier à documenter, faute d'être lancé avec.

    Le glisser-déposer du `.pbip` dans la fenêtre est la voie la plus sûre :
    il écrit le chemin complet, entre guillemets, sans faute de frappe
    possible.
    """
    console.question("Quel rapport documenter ?")
    console.note("Déposez le fichier .pbip dans cette fenêtre, ou collez son chemin.")
    return console.ask("Fichier .pbip")
