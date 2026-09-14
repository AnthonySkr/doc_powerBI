"""
Écriture du document Word, à partir des métadonnées et des images.

Ce module ne lit ni le `.pbip` ni Power BI : tout ce qu'il sait du rapport lui
est passé en argument. C'est ce qui permet de le relancer autant de fois qu'on
veut sur les mêmes données — mettre au point un plan ne demande pas de relire
le projet à chaque essai.

    writer.py          le point d'entrée : `write_document`
    context.py         assemble les collections que le plan parcourt
    filters.py         tables, mesures et étapes retenues par `data:`
    references.py      tableaux numérotés, « utilisée dans »
    measure_links.py   repérage des mentions de mesures dans un texte
    word/              écriture du .docx
    merge/             régénération au-dessus d'une documentation existante
"""

from report_generator.writer import (
    DocumentError,
    DocumentResult,
    output_directory,
    report_result,
    write_document,
)

__all__ = [
    "DocumentError",
    "DocumentResult",
    "output_directory",
    "report_result",
    "write_document",
]
