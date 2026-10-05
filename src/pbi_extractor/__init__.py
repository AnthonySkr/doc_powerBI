"""
Lecture d'un projet Power BI : du `.pbip` aux métadonnées.

Le seul module qui touche au projet : il lit, croise, et retourne un
`PowerBiMetadata`. Il n'écrit aucun fichier et n'ouvre aucune fenêtre.

    extractor.py      le point d'entrée : `open_project` puis `extract`
    pbip.py           les dossiers d'un projet .pbip
    tmdl/             modèle sémantique : tables, mesures DAX, Power Query
    report/           rapport PBIR : pages, groupes, visuels, filtres
    dependencies.py   dépendances transitives entre mesures
"""

from src.pbi_extractor.extractor import ExtractError, extract, open_project
from src.pbi_extractor.pbip import PbipProject

__all__ = ["ExtractError", "PbipProject", "extract", "open_project"]
