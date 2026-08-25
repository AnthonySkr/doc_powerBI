"""
Les réponses données au lancement sont reproposées à la génération suivante.

Une question a des conséquences lourdes : celle des visuels à ne pas détailler.
Oublier d'en re-cocher un le fait réapparaître ; en cocher un de plus fait
disparaître la partie correspondante, et la rédaction qui allait avec.
"""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from src import console
from src.cli import answers, prompts
from src.config import DocConfig

PLAN = {
    "document": {"answers_file": "reponses_{{ report.name }}.yaml"},
    "inputs": [
        {"id": "titre", "type": "text", "label": "Titre", "default": "Rapport"},
        {"id": "detail", "type": "confirm", "label": "Détailler ?", "default": False},
        {
            "id": "ecartes",
            "type": "multi_choice",
            "label": "Visuels à écarter",
            "options": ["Bandeau", "Logo", "Menu"],
        },
    ],
}


class Report:
    name = "RapportDemo"


def config(**document) -> DocConfig:
    plan = {**PLAN, "document": {**PLAN["document"], **document}}
    return DocConfig(plan)


class AnswersFileTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = self._directory.name

    def path(self, **document) -> str:
        return answers.path(config(**document), {"report": Report()}, self.directory)

    def test_nom_du_fichier_construit_sur_le_rapport(self):
        self.assertEqual(self.path(), os.path.join(self.directory, "reponses_RapportDemo.yaml"))

    def test_memoire_desactivable(self):
        self.assertEqual(self.path(remember_answers=False), "")

    def test_aller_retour(self):
        written = {"titre": "Ventes 2026", "detail": True, "ecartes": ["Bandeau", "Logo"]}
        answers.write(self.path(), written)
        with console.silenced():
            self.assertEqual(answers.read(self.path()), written)

    def test_absence_de_fichier(self):
        self.assertEqual(answers.read(self.path()), {})

    def test_fichier_illisible_ignore(self):
        with open(self.path(), "w", encoding="utf-8") as f:
            f.write("::: pas du yaml :::")
        with console.silenced():
            self.assertEqual(answers.read(self.path()), {})

    def test_fichier_qui_n_est_pas_un_dictionnaire_ignore(self):
        with open(self.path(), "w", encoding="utf-8") as f:
            f.write("- une\n- liste\n")
        with console.silenced():
            self.assertEqual(answers.read(self.path()), {})

    def test_rien_a_conserver(self):
        answers.write(self.path(), {})
        self.assertFalse(os.path.exists(self.path()))


class RememberedDefaultsTest(unittest.TestCase):
    """En mode `--no-input`, les réponses d'hier priment sur celles du plan."""

    def context(self) -> dict:
        return {"report": Report(), "inputs": {}, "styles": {}, "choices": {"visuals": []}}

    def test_sans_memoire_les_valeurs_du_plan(self):
        retained = prompts.default_inputs(config(), self.context())
        self.assertEqual(retained["titre"], "Rapport")
        self.assertIs(retained["detail"], False)

    def test_la_memoire_prime(self):
        remembered = {"titre": "Ventes 2026", "ecartes": ["Bandeau"]}
        retained = prompts.default_inputs(config(), self.context(), remembered)
        self.assertEqual(retained["titre"], "Ventes 2026")
        self.assertEqual(retained["ecartes"], ["Bandeau"])

    def test_une_question_absente_de_la_memoire_garde_son_defaut(self):
        retained = prompts.default_inputs(config(), self.context(), {"titre": "Ventes"})
        self.assertIs(retained["detail"], False)


class RememberedPromptsTest(unittest.TestCase):
    """En interactif, un simple Entrée reconduit la réponse précédente."""

    def ask(self, typed: list[str], remembered: dict) -> dict:
        """Pose les questions en simulant une saisie clavier, ligne à ligne."""
        keyboard = io.StringIO("\n".join(typed) + "\n")
        context = {"report": Report(), "inputs": {}, "styles": {}, "choices": {"visuals": []}}
        with (
            mock.patch("sys.stdin", keyboard),
            contextlib.redirect_stdout(io.StringIO()),
            console.silenced(),
        ):
            return prompts.ask_inputs(config(), context, remembered)

    def test_valeur_du_plan_substituee(self):
        """Un `default:` est une expression : sans substitution, c'est `{{ ... }}`
        qui s'écrirait dans le document."""
        retained = self.ask(["", "", ""], {})
        self.assertEqual(retained["titre"], "Rapport")

    def test_valeur_du_plan_construite_sur_une_reponse_precedente(self):
        plan = {
            **PLAN,
            "inputs": [
                {"id": "titre", "type": "text", "label": "Titre", "default": "{{ report.name }}"},
                {
                    "id": "entete",
                    "type": "text",
                    "label": "En-tête",
                    "default": "{{ inputs.titre }}",
                },
            ],
        }
        keyboard = io.StringIO("\n\n")
        context = {"report": Report(), "inputs": {}, "styles": {}, "choices": {"visuals": []}}
        with (
            mock.patch("sys.stdin", keyboard),
            contextlib.redirect_stdout(io.StringIO()),
            console.silenced(),
        ):
            retained = prompts.ask_inputs(DocConfig(plan), context, {})
        self.assertEqual(retained, {"titre": "RapportDemo", "entete": "RapportDemo"})

    def test_reponse_memorisee_reprise_telle_quelle(self):
        """Une réponse est du texte de l'utilisateur : elle n'est pas réinterprétée."""
        retained = self.ask(["", "", ""], {"titre": "Marge {{ brute }}"})
        self.assertEqual(retained["titre"], "Marge {{ brute }}")

    def test_entree_reconduit_tout(self):
        remembered = {"titre": "Ventes 2026", "detail": True, "ecartes": ["Bandeau", "Menu"]}
        retained = self.ask(["", "", ""], remembered)
        self.assertEqual(retained, remembered)

    def test_selection_multiple_modifiable(self):
        retained = self.ask(["", "", "2"], {"ecartes": ["Bandeau"]})
        self.assertEqual(retained["ecartes"], ["Logo"])


if __name__ == "__main__":
    unittest.main()
