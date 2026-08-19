"""
Régénération incrémentale du document.

Plutôt que d'écraser la documentation existante, le script la lit, la compare
au rapport Power BI actuel et écrit un document neuf qui reprend les textes
rédigés par l'utilisateur.

    previous = merge.read_previous(chemin, placeholders)
    ...                                    (écriture, voir generators.word)
    previous.removed(log.written_ids)

Le repérage repose sur des marqueurs invisibles posés à la génération
(`merge.markers`) : identifiant et empreinte technique de chaque élément,
bornes des zones rédigées par l'utilisateur.
"""

from src.merge.changes import ChangeLog
from src.merge.markers import Marker
from src.merge.previous import CHANGED, NEW, UNCHANGED, PreviousDocument
from src.merge.previous import read as read_previous

__all__ = [
    "CHANGED",
    "NEW",
    "UNCHANGED",
    "ChangeLog",
    "Marker",
    "PreviousDocument",
    "read_previous",
]
