"""
Réécriture au lancement des textes types du plan.

Un bloc marqué `editable:` porte dans le YAML un texte par défaut — une phrase
d'introduction, un avertissement. Quand l'utilisateur le demande, chacun lui est
proposé avant d'être écrit : il le garde d'un Entrée, ou le remplace.

Sans cette option, le texte du plan est conservé tel quel et le document ne pose
aucune question.
"""

from collections.abc import Callable
from typing import Any

from src import console
from src.cli import questions

# Callback attendu par le générateur : (bloc du plan, texte du plan) -> texte.
TextProvider = Callable[[dict[str, Any], str], str]


def make_text_provider(enabled: bool) -> TextProvider | None:
    """Retourne le callback de réécriture, ou None si l'option est désactivée."""
    if not enabled:
        return None
    return _propose


def _propose(block: dict[str, Any], default_text: str) -> str:
    console.question(block.get("prompt") or block.get("id") or "texte")
    console.note(f"« {default_text} »")
    if not questions.confirm("Modifier ce texte ?", False):
        return default_text

    console.note("Nouveau texte, puis une ligne vide pour terminer :")
    return questions.lines() or default_text
