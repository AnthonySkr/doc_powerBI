"""
Les réponses aux questions du plan, sans dialogue.

La section `inputs:` de `config_doc_pbi.yaml` déclare des questions ; leurs
réponses entrent dans le contexte du document. Deux façons de les obtenir :

    les demander           `cli.prompts` — l'utilisateur répond
    les déduire du plan    ici — `--no-input`, et toute exécution sans terminal

Le parcours, lui, est le même dans les deux cas : c'est `collect` qui le tient.
Chaque réponse entre aussitôt dans le contexte, si bien qu'une question peut
s'appuyer sur celles qui la précèdent.

Ce module vit dans `shared` parce que l'application « document », lancée seule,
a besoin des réponses sans avoir à dialoguer — ni à dépendre du terminal.
"""

from collections.abc import Callable
from typing import Any

from src.shared.config import DocConfig, render
from src.shared.models import PowerBIReport
from src.shared.selection import documentable_titles

__all__ = ["Answer", "base_context", "collect", "default_inputs", "rendered"]

# Répond à une question : (bloc du plan, contexte, valeur proposée) -> réponse.
Answer = Callable[[dict[str, Any], dict[str, Any], Any], Any]


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
        default = item.get("default")
        proposed = remembered[key] if key in remembered else rendered(default, current)
        answers[key] = answer(item, current, proposed)

    return answers


def rendered(value: Any, context: dict[str, Any]) -> Any:
    """Valeur par défaut du plan, ses `{{ ... }}` substitués."""
    return render(value, context) if isinstance(value, str) else value
