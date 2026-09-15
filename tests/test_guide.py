"""
Tests du mode d'emploi lu dans le terminal.

Le `README.md` livré est aussi ce que l'application affiche. Ce qui est vérifié
ici : qu'il en sort un texte de console lisible — plus une seule balise
Markdown, rien qui déborde de la largeur, les paragraphes recollés — et que le
fichier est cherché là où il est réellement livré.
"""

import os
import unittest
from unittest import mock

from src import __version__, console
from src.cli import guide


def plain(lines: list[str]) -> list[str]:
    return [guide._plain(line) for line in lines]


def joined(lines: list[str]) -> str:
    return "\n".join(plain(lines))


class BalisesTest(unittest.TestCase):
    """Aucune balise Markdown ne doit atteindre l'écran."""

    def test_gras_code_et_italique_otes(self):
        rendered = joined(guide.render("Un **gras**, du `code` et de l'*italique*."))
        self.assertEqual(rendered.strip(), "Un gras, du code et de l'italique.")

    def test_styles_imbriques(self):
        # Le mode d'emploi écrit réellement cette forme : du code dans du gras.
        rendered = joined(guide.render("au **format projet** (`.pbip`)"))
        self.assertEqual(rendered.strip(), "au format projet (.pbip)")

    def test_pas_de_ponctuation_disloquee(self):
        """Une balise collée à son voisin ne doit pas ouvrir un mot."""
        rendered = joined(guide.render("Enregistrer sous **Projet** (`.pbip`)."))
        self.assertIn("(.pbip).", rendered)

    def test_lien_suivi_de_son_adresse(self):
        rendered = joined(guide.render("Voir [la doc](https://exemple.fr)."))
        self.assertIn("la doc (https://exemple.fr)", rendered)


class ParagraphesTest(unittest.TestCase):
    """Les lignes d'un même paragraphe sont recollées avant d'être recoupées."""

    def test_lignes_recollees(self):
        rendered = joined(guide.render("Une phrase\ncoupée\nà la main."))
        self.assertIn("Une phrase coupée à la main.", rendered)

    def test_paragraphes_separes_par_une_ligne_vide(self):
        rendered = plain(guide.render("Premier.\n\nSecond."))
        body = [line.strip() for line in rendered if line.strip()]
        self.assertEqual(body, ["Premier.", "Second."])

    def test_gras_a_cheval_sur_deux_lignes(self):
        rendered = joined(guide.render("Dans Power BI : **Fichier →\nEnregistrer sous**."))
        self.assertIn("Fichier → Enregistrer sous.", rendered)

    def test_largeur_respectee(self):
        long_text = "mot " * 80
        for line in plain(guide.render(long_text)):
            self.assertLessEqual(len(line), console.WIDTH)


class BlocsTest(unittest.TestCase):
    def test_titre_de_niveau_1_encadre(self):
        rendered = plain(guide.render("# Documentation"))
        self.assertTrue(any("DOCUMENTATION" in line for line in rendered))
        self.assertTrue(any(line.startswith(console.glyph("tl")) for line in rendered))

    def test_titre_de_niveau_2_sur_une_ligne_de_separation(self):
        rendered = plain(guide.render("## Prérequis"))
        head = next(line for line in rendered if "Prérequis" in line)
        self.assertTrue(head.startswith(console.glyph("h")))

    def test_liste_a_puces(self):
        rendered = joined(guide.render("- premier point\n- second point"))
        self.assertEqual(rendered.count(console.glyph("dot")), 2)

    def test_liste_numerotee_et_sa_suite_alignee(self):
        rendered = plain(guide.render("1. Glissez le fichier\n   sur l'exécutable."))
        body = [line for line in rendered if line.strip()]
        self.assertEqual(body, ["  1. Glissez le fichier sur l'exécutable."])

    def test_citation_sur_plusieurs_lignes(self):
        rendered = plain(guide.render("> Vos réponses\n> sont conservées."))
        body = [line for line in rendered if line.strip()]
        self.assertEqual(len(body), 1)
        self.assertIn("Vos réponses sont conservées.", body[0])

    def test_bloc_de_code_laisse_intact(self):
        rendered = joined(guide.render("```\nMon rapport.pbip\n  indenté\n```"))
        self.assertIn("Mon rapport.pbip", rendered)
        self.assertIn("  indenté", rendered)

    def test_bloc_de_code_non_recolle(self):
        """Deux lignes de code restent deux lignes — ce n'est pas un paragraphe."""
        rendered = [line for line in plain(guide.render("```\nune\ndeux\n```")) if line.strip()]
        self.assertEqual(len(rendered), 2)

    def test_trait_de_separation(self):
        rendered = plain(guide.render("Avant\n\n---\n\nAprès"))
        self.assertTrue(any(set(line.strip()) == {console.glyph("h")} for line in rendered))


class TableauTest(unittest.TestCase):
    SOURCE = (
        "| Fichier | À quoi il sert |\n"
        "| --- | --- |\n"
        "| `powerbi-doc.exe` | L'application |\n"
        "| `config_doc_pbi.yaml` | Le plan du document |\n"
    )

    def setUp(self):
        self.rendered = plain(guide.render(self.SOURCE))

    def test_ligne_de_separation_markdown_absente(self):
        self.assertNotIn("---", "\n".join(self.rendered))

    def test_colonnes_alignees(self):
        body = [line for line in self.rendered if console.glyph("v") in line]
        positions = {line.index(console.glyph("v")) for line in body}
        self.assertEqual(len(positions), 1)

    def test_contenu_conserve(self):
        joined_lines = "\n".join(self.rendered)
        self.assertIn("powerbi-doc.exe", joined_lines)
        self.assertIn("L'application", joined_lines)

    def test_cellule_large_repliee_dans_sa_colonne(self):
        wide = "| Message | Que faire |\n| --- | --- |\n| Court | " + "mot " * 40 + "|\n"
        for line in plain(guide.render(wide)):
            self.assertLessEqual(len(line), console.WIDTH)


class ModeEmploiLivreTest(unittest.TestCase):
    """Le fichier réellement distribué doit passer la mise en page."""

    def setUp(self):
        self.rendered = guide.render(guide._read() or "")

    def test_mode_emploi_trouve_en_developpement(self):
        self.assertTrue(os.path.isfile(guide.candidates()[0]))
        self.assertTrue(self.rendered)

    def test_version_inscrite(self):
        self.assertIn(f"Version {__version__}", joined(self.rendered))
        self.assertNotIn("{version}", joined(self.rendered))

    def test_aucune_balise_restante(self):
        body = joined(self.rendered)
        for marker in ("**", "##", "| ---"):
            self.assertNotIn(marker, body)

    def test_largeur_respectee_hors_blocs_de_code(self):
        # Les blocs de code sont recopiés tels quels : leur largeur appartient
        # à l'auteur du mode d'emploi, pas à la mise en page.
        code = console.glyph("v")
        for line in plain(self.rendered):
            if line.lstrip().startswith(code):
                continue
            self.assertLessEqual(len(line), console.WIDTH, line)


class EmplacementTest(unittest.TestCase):
    def test_cherche_dans_tools_en_developpement(self):
        with mock.patch.object(guide.paths, "is_frozen", return_value=False):
            self.assertEqual(
                guide.candidates(),
                [os.path.join(guide.paths.app_dir(), "tools", guide.README)],
            )

    def test_a_cote_de_l_executable_puis_dans_le_bundle(self):
        with (
            mock.patch.object(guide.paths, "is_frozen", return_value=True),
            mock.patch.object(guide.paths, "app_dir", return_value="/appli"),
            mock.patch.object(guide.paths, "bundled_dir", return_value="/bundle"),
        ):
            self.assertEqual(
                guide.candidates(),
                [
                    os.path.join("/appli", guide.README),
                    os.path.join("/bundle", guide.README),
                ],
            )

    def test_copie_embarquee_si_le_fichier_livre_manque(self):
        with (
            mock.patch.object(guide, "candidates", return_value=["/absent/README.md", "ok"]),
            mock.patch("builtins.open", mock.mock_open(read_data="v{version}")) as opened,
        ):
            opened.side_effect = [OSError("absent"), mock.mock_open(read_data="v{version}")()]
            self.assertEqual(guide._read(), f"v{__version__}")


class AffichageTest(unittest.TestCase):
    def test_introuvable_signale_sans_faire_echouer(self):
        with (
            mock.patch.object(guide, "_read", return_value=None),
            mock.patch.object(guide.console, "error") as reported,
            mock.patch.object(guide.console, "detail"),
            mock.patch("builtins.print"),
        ):
            guide.show()
        reported.assert_called_once()

    def test_pas_de_pagination_hors_terminal(self):
        """Sortie redirigée : personne pour appuyer sur une touche."""
        with (
            mock.patch.object(guide.console, "is_terminal", return_value=False),
            mock.patch.object(guide.console, "height", return_value=0),
            mock.patch("builtins.input") as prompted,
            mock.patch("builtins.print"),
        ):
            guide.show()
        prompted.assert_not_called()

    def test_pagination_ecran_par_ecran(self):
        with (
            mock.patch.object(guide.console, "is_terminal", return_value=True),
            mock.patch.object(guide.console, "height", return_value=10),
            mock.patch("builtins.input", return_value="") as prompted,
            mock.patch("builtins.print"),
        ):
            guide.show()
        self.assertGreater(prompted.call_count, 1)

    def test_q_interrompt_la_lecture(self):
        with (
            mock.patch.object(guide.console, "is_terminal", return_value=True),
            mock.patch.object(guide.console, "height", return_value=10),
            mock.patch("builtins.input", return_value="q") as prompted,
            mock.patch("builtins.print"),
        ):
            guide.show()
        self.assertEqual(prompted.call_count, 1)

    def test_entree_fermee_ne_bloque_pas(self):
        with (
            mock.patch.object(guide.console, "is_terminal", return_value=True),
            mock.patch.object(guide.console, "height", return_value=10),
            mock.patch("builtins.input", side_effect=RuntimeError("lost sys.stdin")),
            mock.patch("builtins.print"),
        ):
            guide.show()  # ne doit pas remonter


if __name__ == "__main__":
    unittest.main()
