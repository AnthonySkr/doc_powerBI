"""
Lecture d'un projet Power BI : du `.pbip` aux métadonnées.

C'est le seul module qui touche au projet Power BI. Il lit, croise, et retourne
un `PowerBiMetadata` — il n'écrit aucun fichier et n'ouvre aucune fenêtre.

    extractor.py      le point d'entrée : `open_project` puis `extract`
    pbip.py           les dossiers d'un projet .pbip
    tmdl/             modèle sémantique : tables, mesures DAX, Power Query
    report/           rapport PBIR : pages, groupes, visuels, filtres
    dependencies.py   dépendances transitives entre mesures
"""

from pbi_extractor.extractor import ExtractError, extract, open_project
from pbi_extractor.pbip import PbipProject

__all__ = ["ExtractError", "PbipProject", "extract", "open_project"]
