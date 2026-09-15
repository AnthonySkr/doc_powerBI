"""
Les questions posées au lancement, et les réponses qui en sortent.

La section `inputs:` du plan déclare les questions ; leurs réponses entrent
dans le contexte du document. Le parcours est le même qu'on les pose ou non —
c'est `collect` qui le tient — et seule change la façon de répondre :

    `ask_inputs`      l'utilisateur répond au terminal
    `default_inputs`  la valeur proposée est retenue telle quelle (`--no-input`)

Chaque réponse entre aussitôt dans le contexte, si bien qu'une question peut
s'appuyer sur celles qui la précèdent. La valeur proposée est celle de la
génération précédente quand il y en a une (voir `core.answers`), sinon le
`default:` du plan : on valide d'un Entrée.

S'y ajoute la réécriture des textes types du plan — un bloc marqué `editable:`
est proposé avant d'être écrit, à qui le demande.
"""

from collections.abc import Callable
from typing import Any

from core import console, questions
from core.config import DocConfig
from core.expressions import evaluate, render, resolve_items
from core.models import PowerBIReport
from core.selection import documentable_titles

__all__ = [
    "Answer",
    "TextProvider",
    "ask_inputs",
    "base_context",
    "collect",
    "default_inputs",
    "make_text_provider",
]

# Répond à une question : (bloc du plan, contexte, valeur proposée) -> réponse.
Answer = Callable[[dict[str, Any], dict[str, Any], Any], Any]

# Réécrit un texte du plan : (bloc du plan, texte du plan) -> texte retenu.
TextProvider = Callable[[dict[str, Any], str], str]


# ─────────────────────────────────────────────────────────────
#  Le parcours, commun aux deux façons de répondre
# ─────────────────────────────────────────────────────────────


def base_context(report: PowerBIReport, config: DocConfig) -> dict[str, Any]:
    """
    Contexte dans lequel les questions du plan sont évaluées.

    `choices` : ce que le rapport contient réellement, pour les questions qui
    font choisir dans son contenu plutôt que dans une liste figée du YAML.
    """
    return {
        "report": report,
        "inputs": {},
        "styles": config.styles,
        "choices": {"visuals": documentable_titles(report, config)},
    }


def collect(
    config: DocConfig,
    context: dict[str, Any],
    remembered: dict[str, Any] | None,
    answer: Answer,
) -> dict[str, Any]:
    """Déroule les questions du plan et rassemble les réponses."""
    remembered = remembered or {}
    answers: dict[str, Any] = {}

    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue

        current = {**context, "inputs": answers}
        # La réponse d'hier est reprise telle quelle — c'est du texte de
        # l'utilisateur. Le `default:` du plan, lui, est une expression : il
        # est substitué, faute de quoi c'est `{{ ... }}` qui s'écrirait dans le
        # document.
        proposed = remembered[key] if key in remembered else _rendered(item.get("default"), current)
        answers[key] = answer(item, current, proposed)

    return answers


def default_inputs(
    config: DocConfig, context: dict[str, Any], remembered: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Réponses retenues sans rien demander (`--no-input`).

    Celles de la génération précédente d'abord : une exécution automatisée
    reconduit ainsi les choix faits la dernière fois, plutôt que de repartir des
    valeurs figées du plan et de défaire le document.
    """
    return collect(config, context, remembered, lambda _item, _ctx, proposed: proposed)


def _rendered(value: Any, context: dict[str, Any]) -> Any:
    """Valeur par défaut du plan, ses `{{ ... }}` substitués."""
    return render(value, context) if isinstance(value, str) else value


# ─────────────────────────────────────────────────────────────
#  Les poser à l'utilisateur
# ─────────────────────────────────────────────────────────────


def ask_inputs(
    config: DocConfig,
    context: dict[str, Any],
    remembered: dict[str, Any] | None = None,
    step: tuple[int, int] | tuple[()] = (),
) -> dict[str, Any]:
    """Pose les questions déclarées dans le plan."""
    if not config.inputs:
        return {}

    console.step("Renseignements", *step)
    console.note("Entrée valide la valeur proposée entre crochets.")
    answers = collect(config, context, remembered, _ask)
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


# ─────────────────────────────────────────────────────────────
#  Réécrire les textes types du plan
# ─────────────────────────────────────────────────────────────


def make_text_provider(enabled: bool) -> TextProvider | None:
    """
    Retourne de quoi proposer la réécriture des textes, ou None.

    Un bloc marqué `editable:` porte dans le YAML un texte par défaut — une
    phrase d'introduction, un avertissement. Quand l'utilisateur le demande,
    chacun lui est proposé avant d'être écrit : il le garde d'un Entrée, ou le
    remplace. Sans l'option, le texte du plan est conservé tel quel et le
    document ne pose aucune question.
    """
    return _propose if enabled else None


def _propose(block: dict[str, Any], default_text: str) -> str:
    console.question(block.get("prompt") or block.get("id") or "texte")
    console.note(f"« {default_text} »")
    if not questions.confirm("Modifier ce texte ?", False):
        return default_text

    console.note("Nouveau texte, puis une ligne vide pour terminer :")
    return questions.lines() or default_text
