"""
Questions posées à l'utilisateur au lancement.

Les questions ne sont pas codées ici : elles sont déclarées dans la section
`inputs:` de la configuration. Ce module se contente de les afficher selon leur
`type` (text, textarea, confirm, choice, multi_choice) et de collecter les
réponses.

La valeur proposée est celle de la génération précédente quand il y en a une
(voir `cli.answers`), sinon le `default:` du plan : on valide d'un Entrée.
"""

from typing import Any

from src import console
from src.config import DocConfig, evaluate, render, resolve_items

# Callback proposant de réécrire le texte d'un bloc `editable`.
TextProvider = Any


def ask_inputs(
    config: DocConfig, base_context: dict[str, Any], remembered: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Pose les questions déclarées dans la configuration."""
    if not config.inputs:
        return {}

    console.step("Renseignements")
    remembered = remembered or {}

    answers: dict[str, Any] = {}
    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue

        context = {**base_context, "inputs": answers}
        label = render(item.get("label") or key, context)
        kind = item.get("type", "text")

        options = resolve_items(item.get("options"), context)
        # La réponse d'hier est reprise telle quelle — c'est du texte de
        # l'utilisateur. Le `default:` du plan, lui, est une expression : il
        # est substitué, faute de quoi c'est `{{ ... }}` qui s'écrirait dans le
        # document.
        proposed = remembered[key] if key in remembered else _rendered(item.get("default"), context)

        if kind == "confirm":
            answers[key] = ask_confirm(label, evaluate(proposed, context))
        elif kind == "choice":
            answers[key] = _ask_choice(label, options, proposed)
        elif kind == "multi_choice":
            answers[key] = _ask_multi_choice(label, options, _as_list(proposed))
        else:
            answers[key] = _ask_text(label, proposed, multiline=(kind == "textarea"))

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
    remembered = remembered or {}
    answers: dict[str, Any] = {}
    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue
        if key in remembered:
            answers[key] = remembered[key]
            continue
        context = {**base_context, "inputs": answers}
        answers[key] = _rendered(item.get("default"), context)
    return answers


def _rendered(value: Any, context: dict[str, Any]) -> Any:
    """Valeur par défaut du plan, ses `{{ ... }}` substitués."""
    return render(value, context) if isinstance(value, str) else value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple, set)) else [value]


def make_text_provider(enabled: bool):
    """
    Retourne le callback proposant à l'utilisateur de modifier les textes types
    des blocs `editable`. Si désactivé, le texte du YAML est conservé.
    """
    if not enabled:
        return None

    def provider(block: dict[str, Any], default_text: str) -> str:
        label = block.get("prompt") or block.get("id") or "texte"
        print()
        print(f"  ── {label}")
        print(f"     « {default_text} »")
        if not ask_confirm("     Modifier ce texte ?", False):
            return default_text
        print("     Nouveau texte (ligne vide pour terminer) :")
        return _read_lines("     > ") or default_text

    return provider


# ─────────────────────────────────────────────────────────────
#  Types de question
# ─────────────────────────────────────────────────────────────


def ask_confirm(label: str, default: bool) -> bool:
    hint = "[O/n]" if default else "[o/N]"
    answer = input(f"  {label} {hint} ").strip().lower()
    if not answer:
        return default
    return answer in ("o", "oui", "y", "yes", "1")


def _ask_text(label: str, default: str, multiline: bool = False) -> str:
    if multiline:
        print(f"  {label} (ligne vide pour terminer)")
        return _read_lines("  > ") or default

    suffix = f" [{default}]" if default else ""
    return input(f"  {label}{suffix} : ").strip() or default


def _ask_choice(label: str, options: list[Any], default: Any) -> Any:
    print(f"  {label}")
    for index, option in enumerate(options, start=1):
        retained = "  ←" if default is not None and option == default else ""
        print(f"    {index}. {option}{retained}")

    answer = input(f"  Choix [1-{len(options)}] : ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        return options[int(answer) - 1]
    return default if default is not None else (options[0] if options else "")


def _ask_multi_choice(label: str, options: list[Any], default: list[Any]) -> list[Any]:
    """
    Sélection multiple : l'utilisateur entre les numéros qui l'intéressent.

    Sans option à proposer, la question n'est pas posée — il n'y a rien à
    choisir dans ce rapport.

    Une réponse vide reconduit la sélection précédente : c'est le geste le plus
    naturel, et il ne doit rien défaire.
    """
    if not options:
        return list(default)

    print(f"  {label}")
    for index, option in enumerate(options, start=1):
        retained = "  ←" if option in default else ""
        print(f"    {index}. {option}{retained}")

    # Les réponses de la dernière génération sont marquées d'une flèche : les
    # reconduire d'un Entrée évite de faire disparaître une partie déjà rédigée.
    keep = f"vide = {'inchangé' if default else 'aucun'}"
    answer = input(f"  Numéros séparés par une virgule ({keep}) : ").strip()
    if not answer:
        return list(default)

    chosen: list[Any] = []
    ignored: list[str] = []
    for piece in answer.replace(";", ",").split(","):
        piece = piece.strip()
        if piece.isdigit() and 1 <= int(piece) <= len(options):
            option = options[int(piece) - 1]
            if option not in chosen:
                chosen.append(option)
        elif piece:
            ignored.append(piece)

    if ignored:
        console.warn(f"Réponse ignorée : {', '.join(ignored)}")
    return chosen


def _read_lines(prompt: str) -> str:
    """Lit plusieurs lignes jusqu'à une ligne vide."""
    lines: list[str] = []
    while True:
        line = input(prompt)
        if not line.strip():
            return "\n".join(lines)
        lines.append(line)
