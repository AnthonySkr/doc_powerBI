"""
Application « document » : du fichier d'échange au .docx.

    python -m src.apps.document

Elle ne lit ni le `.pbip` ni Power BI : tout ce qu'elle sait du rapport vient du
fichier que les applications précédentes lui ont laissé. C'est ce qui permet de
la relancer autant de fois qu'on veut sur les mêmes données — mettre au point un
plan de document ne demande pas de relire le projet à chaque essai.

    context.py         assemble les collections que le plan parcourt
    filters.py         tables, mesures et étapes retenues par `data:`
    references.py      tableaux numérotés, « utilisée dans »
    measure_links.py   repérage des mentions de mesures dans un texte
    word/              écriture du .docx
    merge/             régénération au-dessus d'une documentation existante
"""

from src.apps.document.context import build_context
from src.apps.document.word import DocumentError, generate_word_documentation

__all__ = ["DocumentError", "build_context", "generate_word_documentation"]
