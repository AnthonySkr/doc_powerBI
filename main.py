"""
Génération de la documentation Word d'un rapport Power BI (.pbip).

    python main.py "C:\\chemin\\Rapport.pbip"

La structure du document est décrite dans `config_doc_pbi.yaml` ; le code se
contente de collecter les données du .pbip et de suivre ce plan.
"""

import sys

from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
