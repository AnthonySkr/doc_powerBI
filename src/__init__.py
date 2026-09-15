"""
Génération de la documentation Word d'un rapport Power BI (.pbip).

La version est déclarée ici, et nulle part ailleurs : `pyproject.toml` la lit
depuis ce module (`[tool.setuptools.dynamic]`), l'outil de distribution la lit
pour nommer l'archive, et le bandeau du script l'affiche. Un exécutable
n'embarque pas les métadonnées de son paquet — sans cette constante, il serait
le seul à ne pas savoir quelle version il est.
"""

__version__ = "1.0.0"
