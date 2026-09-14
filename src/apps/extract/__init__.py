"""
Application « extraction » : d'un projet `.pbip` au fichier d'échange.

    python -m src.apps.extract rapport.pbip

Elle lit le modèle sémantique (`.SemanticModel/`) et le rapport (`.Report/`),
croise les deux, et écrit tout ce que la suite de la chaîne aura besoin de
savoir. C'est la seule application qui touche au `.pbip` : les suivantes ne
travaillent plus que sur son fichier.

    pbip.py           localisation des dossiers d'un projet .pbip
    collect.py        l'extraction proprement dite
    tmdl/             modèle sémantique : tables, mesures, Power Query
    report/           rapport PBIR : pages, groupes, visuels, filtres
    dependencies.py   dépendances transitives entre mesures
"""

from src.apps.extract.collect import ExtractError, collect, open_project
from src.apps.extract.pbip import PbipProject

__all__ = ["ExtractError", "PbipProject", "collect", "open_project"]
