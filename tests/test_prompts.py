"""Tests des questions posées au lancement (`inputs:`)."""

import contextlib
import io
import unittest
from unittest import mock

from src.cli import prompts
from src.config import DocConfig


def config(*inputs) -> DocConfig:
    return DocConfig({"inputs": list(inputs)})


def answer(config_, base_context, typed: str):
    """Pose les questions en simulant une saisie clavier."""
    with mock.patch("sys.stdin", io.StringIO(typed + "\n")), _silent():
        return prompts.ask_inputs(config_, base_context)


def _silent():
    """Retient l'affichage : les questions écrivent sur la sortie standard."""
    return contextlib.redirect_stdout(io.StringIO())


class MultiChoiceTest(unittest.TestCase):
    """Sélection multiple parmi les options proposées."""

    def setUp(self):
        self.question = {
            "id": "exclus",
            "type": "multi_choice",
            "label": "À ne pas détailler",
            "options": "{{ choices.visuals }}",
            "default": [],
        }
        self.context = {"choices": {"visuals": ["En-tête", "CA", "Détail"]}, "styles": {}}

    def _ask(self, typed: str):
        return answer(config(self.question), self.context, typed)["exclus"]

    def test_selection_par_numeros(self):
        self.assertEqual(self._ask("1, 3"), ["En-tête", "Détail"])

    def test_reponse_vide_ne_selectionne_rien(self):
        self.assertEqual(self._ask(""), [])

    def test_doublons_et_numeros_hors_liste_ignores(self):
        self.assertEqual(self._ask("2;2;9;abc"), ["CA"])

    def test_sans_option_la_question_ne_bloque_pas(self):
        self.context["choices"]["visuals"] = []
        refuse = mock.patch("builtins.input", side_effect=AssertionError("ne doit rien demander"))
        with refuse, _silent():
            answers = prompts.ask_inputs(config(self.question), self.context)
        self.assertEqual(answers["exclus"], [])

    def test_valeur_par_defaut_hors_interactif(self):
        answers = prompts.default_inputs(config(self.question), self.context)
        self.assertEqual(answers["exclus"], [])


class ChoiceTest(unittest.TestCase):
    """Les options d'un `choice` peuvent aussi venir du rapport."""

    def test_options_dynamiques(self):
        question = {
            "id": "page",
            "type": "choice",
            "label": "Page principale",
            "options": "{{ choices.pages }}",
        }
        context = {"choices": {"pages": ["Accueil", "Détail"]}, "styles": {}}
        self.assertEqual(answer(config(question), context, "2")["page"], "Détail")


if __name__ == "__main__":
    unittest.main()
