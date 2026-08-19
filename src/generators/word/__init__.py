"""
Écriture du document Word.

    generate_word_documentation(config, context, chemin, text_provider)

Le module est découpé par responsabilité :
    generator.py   ouverture du template, sauvegarde
    document.py    parcours du plan YAML et écriture du contenu
    styles.py      clés de style de la configuration -> styles du template
    links.py       signets et liens internes
    tables.py      réglages OOXML des tableaux
    fields.py      table des matières, en-têtes et pieds de page
    word_app.py    recalcul des champs par Word (optionnel, Windows)
"""

from src.generators.word.document import DocumentBuilder, TextProvider
from src.generators.word.generator import generate_word_documentation

__all__ = ["DocumentBuilder", "TextProvider", "generate_word_documentation"]
