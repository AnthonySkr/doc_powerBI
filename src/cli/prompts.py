"""
Questionnaire posé au lancement, tel que le plan le déclare.

Les questions ne sont pas codées ici : elles sont déclarées dans la section
`inputs:` de la configuration. Ce module lit cette déclaration, la traduit en
questions élémentaires (voir `cli.questions`) et rassemble les réponses.

La valeur proposée est celle de la génération précédente quand il y en a une
(voir `cli.answers`), sinon le `default:` du plan : on valide d'un Entrée.
"""

from collections.abc import Callable
from typing import Any

from src import console
from src.cli import questions
from src.config import DocConfig, evaluate, render, resolve_items

__all__ = ["ask_inputs", "default_inputs"]


def ask_inputs(
    config: DocConfig,
    base_context: dict[str, Any],
    remembered: dict[str, Any] | None = None,
    step: tuple[int, int] | tuple[()] = (),
) -> dict[str, Any]:
    """Pose les questions déclarées dans la configuration."""
    if not config.inputs:
        return {}

    console.step("Renseignements", *step)
    console.note("Entrée valide la valeur proposée entre crochets.")
    answers = _collect(config, base_context, remembered, _ask)
    console.blank()
    return answers


def default_inputs(
    config: DocConfig, base_context: dict[str, Any], remembered: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Réponses retenues sans rien demander (`--no-input`).

    Celles de la génération précédente d'abord : une exécution automatisée
    reconduit ainsi les choix faits la dernière fois, plutôt que de repartir des
    valeurs figées du plan et de défaire le document.
    """
    return _collect(config, base_context, remembered, lambda _item, _ctx, proposed: proposed)


# Répond à une question : (bloc du plan, contexte, valeur proposée) -> réponse.
_Answer = Callable[[dict[str, Any], dict[str, Any], Any], Any]


def _collect(
    config: DocConfig,
    base_context: dict[str, Any],
    remembered: dict[str, Any] | None,
    answer: _Answer,
) -> dict[str, Any]:
    """
    Déroule les questions du plan et rassemble les réponses.

    Le même parcours sert en interactif et en `--no-input` : seule change la
    façon de répondre. Chaque réponse entre aussitôt dans le contexte, si bien
    qu'une question peut s'appuyer sur celles qui la précèdent.
    """
    remembered = remembered or {}
    answers: dict[str, Any] = {}

    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue

        context = {**base_context, "inputs": answers}
        # La réponse d'hier est reprise telle quelle — c'est du texte de
        # l'utilisateur. Le `default:` du plan, lui, est une expression : il
        # est substitué, faute de quoi c'est `{{ ... }}` qui s'écrirait dans le
        # document.
        default = item.get("default")
        proposed = remembered[key] if key in remembered else _rendered(default, context)
        answers[key] = answer(item, context, proposed)

    return answers


def _ask(item: dict[str, Any], context: dict[str, Any], proposed: Any) -> Any:
    """Pose une question du plan selon son `type:`."""
    label = render(item.get("label") or item["id"], context)
    kind = item.get("type", "text")
    options = resolve_items(item.get("options"), context)

    if kind == "confirm":
        return questions.confirm(label, evaluate(proposed, context))
    if kind == "choice":
        return questions.choice(label, options, proposed)
    if kind == "multi_choice":
        return questions.multi_choice(label, options, questions.as_list(proposed))
    return questions.text(label, proposed, multiline=(kind == "textarea"))


def _rendered(value: Any, context: dict[str, Any]) -> Any:
    """Valeur par défaut du plan, ses `{{ ... }}` substitués."""
    return render(value, context) if isinstance(value, str) else value
