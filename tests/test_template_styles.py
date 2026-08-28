"""
Ce que le template livré doit garantir sur ses styles.

Régression : le style « Code DAX » portait un `w:framePr`, c'est-à-dire un
cadre flottant. Sans largeur déclarée, ce cadre s'ajuste à son contenu, et
`wrap="around"` fait remonter le paragraphe suivant dans la place laissée
libre à sa droite. Une formule tenant sur une seule ligne — courte, donc
étroite — voyait ainsi le sous-titre « Description » s'afficher à côté d'elle
plutôt qu'en dessous ; une formule longue ou sur plusieurs lignes occupait
toute la largeur et ne laissait rien passer, d'où un défaut qui ne touchait
qu'une partie des mesures.

Rien dans le générateur ne peut corriger cela : c'est le style du document qui
sort le paragraphe du fil du texte. Le test porte donc sur le template.
"""

import os
import unittest
import zipfile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "template-doc-pbib.docx")


def _styles() -> etree._Element:
    with zipfile.ZipFile(TEMPLATE) as template:
        return etree.fromstring(template.read("word/styles.xml"))


class TemplateStylesTest(unittest.TestCase):
    def test_aucun_style_ne_flotte_hors_du_fil_du_texte(self):
        """
        Un style encadré ferait remonter à côté de lui le contenu qui le suit.

        Le plan écrit des blocs les uns sous les autres et compte sur le
        document pour les afficher ainsi. Un `w:framePr`, où qu'il soit, rompt
        cet ordre — et d'autant plus discrètement qu'il ne se voit que sur les
        contenus assez courts pour laisser de la place à leur droite.
        """
        framed = [
            style.find(W + "name").get(W + "val")
            for style in _styles().iter(W + "style")
            if style.find(f"{W}pPr/{W}framePr") is not None
        ]
        self.assertEqual(
            framed,
            [],
            f"styles encadrés dans le template : {framed}. Le contenu qui suit un "
            "paragraphe de ce style s'affichera à côté de lui, pas en dessous.",
        )

    def test_le_style_du_code_garde_son_aspect(self):
        """Retirer le cadre ne doit pas emporter l'encadré gris du code."""
        for style in _styles().iter(W + "style"):
            name = style.find(W + "name")
            if name is not None and name.get(W + "val") == "Code DAX":
                properties = style.find(W + "pPr")
                kept = {child.tag.replace(W, "") for child in properties}
                self.assertIn("pBdr", kept, "le code n'a plus de bordure")
                self.assertIn("shd", kept, "le code n'a plus son fond gris")
                return
        self.fail("le style « Code DAX » a disparu du template")


if __name__ == "__main__":
    unittest.main()
