"""
Écriture du document Word.

    generate_word_documentation(config, context, chemin, text_provider)

Le module est découpé par responsabilité :

    generator.py   lecture du document précédent, écriture, archivage
    errors.py      `DocumentError`, seule erreur remontée à l'utilisateur
    merging.py     marqueurs, reprise des textes, surlignage
    builder.py     parcours du plan YAML et écriture du contenu
    body.py        insertion en fin de corps, sans reparcourir le document
    styles.py      clés de style du plan → styles du template
    links.py       signets et liens internes
    tables.py      réglages OOXML des tableaux
    figures.py     emplacements d'images : repère, légende, pastilles
    shapes.py      repères numérotés à glisser sur une image
    values.py      lecture des valeurs déclarées dans le plan
    fields.py      table des matières, en-têtes et pieds de page
    word_app.py    recalcul des champs par Word (optionnel, Windows)
"""

from src.report_generator.word.builder import DocumentBuilder, TextProvider
from src.report_generator.word.errors import DocumentError
from src.report_generator.word.generator import generate_word_documentation

__all__ = [
    "DocumentBuilder",
    "DocumentError",
    "TextProvider",
    "generate_word_documentation",
]
