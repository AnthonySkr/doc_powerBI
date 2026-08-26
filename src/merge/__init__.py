"""
Régénération d'une documentation au-dessus de la version existante.

Le principe : **le script est propriétaire de ses données, l'utilisateur du
reste.** À chaque génération, le script réécrit les contenus qu'il produit
(formule DAX, tableau des champs, métadonnées) et recopie tel quel tout le
reste — titres reformulés, notes ajoutées, captures collées, mise en forme.

Les amorces — paragraphes d'exemple, emplacements d'image, zones à compléter —
tiennent des deux : tant que personne n'y a touché, elles suivent le plan ; dès
qu'on y écrit, c'est la version du document qui l'emporte.

    previous = merge.read_previous(chemin)
    ...                                     (génération, voir generators.word)
    merge.apply_merge(document, previous, options, log)

Le repérage passe par des marqueurs invisibles (`merge.markers`) : une ancre
par élément documenté, et un encadrement autour de chaque bloc du plan. Ce qui
a été écrit *à l'intérieur* d'un contenu produit par le script — une
description sous un tableau, une note entre deux valeurs — y est retrouvé et
reposé au même endroit (`merge.salvage`).

Rien n'est perdu quand la place n'existe plus : un élément disparu du rapport,
un bloc retiré du plan, une donnée du script retouchée à la main. Ces contenus
sont rassemblés en fin de document (`merge.orphans`), avec leur provenance.
"""

from src.merge import orphans
from src.merge.changes import ChangeLog
from src.merge.markers import Marker
from src.merge.previous import CHANGED, NEW, UNCHANGED, PreviousDocument
from src.merge.previous import read as read_previous
from src.merge.smart import merge as apply_merge

__all__ = [
    "CHANGED",
    "NEW",
    "UNCHANGED",
    "ChangeLog",
    "Marker",
    "PreviousDocument",
    "apply_merge",
    "orphans",
    "read_previous",
]
