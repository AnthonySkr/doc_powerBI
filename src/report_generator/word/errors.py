"""Erreur commune à l'écriture du document."""


class DocumentError(Exception):
    """
    Le document n'a pas pu être produit.

    Toujours porteuse d'un message rédigé pour l'utilisateur : c'est lui qui
    s'affiche dans la console, sans trace d'exception (voir `main`).
    """
