"""
Questionnaire posé au lancement, tel que le plan le déclare.

Les questions ne sont pas codées ici : elles sont déclarées dans la section
`inputs:` de la configuration. Ce module lit cette déclaration, la traduit en
questions élémentaires (voir `cli.questions`) et rassemble les réponses.

Le parcours est celui de `shared.inputs` — le même qu'en `--no-input` : seule
change la façon de répondre. La valeur proposée est celle de la génération
précédente quand il y en a une (voir `shared.answers`), sinon le `default:` du
plan : on valide d'un Entrée.
"""

from typing import Any

from src.cli import questions
from src.shared import console
from src.shared.config import DocConfig, evaluate, render, resolve_items
from src.shared.inputs import collect

__all__ = ["ask_inputs"]


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
    answers = collect(config, base_context, remembered, _ask)
    console.blank()
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
