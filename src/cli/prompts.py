"""
Questions posées à l'utilisateur au lancement.

Les questions ne sont pas codées ici : elles sont déclarées dans la section
`inputs:` de la configuration. Ce module se contente de les afficher selon leur
`type` (text, textarea, confirm, choice, multi_choice) et de collecter les
réponses.
"""

from typing import Any

from src import console
from src.config import DocConfig, render, resolve_items

# Callback proposant de réécrire le texte d'un bloc `editable`.
TextProvider = Any


def ask_inputs(config: DocConfig, base_context: dict[str, Any]) -> dict[str, Any]:
    """Pose les questions déclarées dans la configuration."""
    if not config.inputs:
        return {}

    console.step("Renseignements")

    answers: dict[str, Any] = {}
    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue

        context = {**base_context, "inputs": answers}
        label = render(item.get("label") or key, context)
        kind = item.get("type", "text")

        options = resolve_items(item.get("options"), context)

        if kind == "confirm":
            answers[key] = ask_confirm(label, bool(item.get("default", False)))
        elif kind == "choice":
            answers[key] = _ask_choice(label, options, item.get("default"))
        elif kind == "multi_choice":
            answers[key] = _ask_multi_choice(label, options, item.get("default") or [])
        else:
            default = render(item.get("default"), context)
            answers[key] = _ask_text(label, default, multiline=(kind == "textarea"))

    console.blank()
    return answers


def default_inputs(config: DocConfig, base_context: dict[str, Any]) -> dict[str, Any]:
    """Valeurs par défaut des `inputs`, utilisées en mode non interactif."""
    answers: dict[str, Any] = {}
    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue
        value = item.get("default")
        context = {**base_context, "inputs": answers}
        answers[key] = render(value, context) if isinstance(value, str) else value
    return answers


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
        print(f"    {index}. {option}")

    answer = input(f"  Choix [1-{len(options)}] : ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        return options[int(answer) - 1]
    return default if default is not None else (options[0] if options else "")


def _ask_multi_choice(label: str, options: list[Any], default: list[Any]) -> list[Any]:
    """
    Sélection multiple : l'utilisateur entre les numéros qui l'intéressent.

    Sans option à proposer, la question n'est pas posée — il n'y a rien à
    choisir dans ce rapport.
    """
    if not options:
        return list(default)

    print(f"  {label}")
    for index, option in enumerate(options, start=1):
        print(f"    {index}. {option}")

    answer = input("  Numéros séparés par une virgule (vide = aucun) : ").strip()
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
