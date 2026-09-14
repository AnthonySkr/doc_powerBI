"""
Questions élémentaires posées au terminal.

Ce module ne sait rien du plan du document : il pose une question d'un type
donné — oui/non, texte, texte long, choix, choix multiple — et retourne la
réponse. C'est `cli.prompts` qui décide lesquelles poser, et `shared.console`
qui sait les dessiner.

Une réponse vide vaut toujours acceptation de la valeur proposée : c'est le
geste le plus courant, et il ne doit rien défaire.
"""

from typing import Any

from src.shared import console

_YES = ("o", "oui", "y", "yes", "1")


def confirm(label: str, default: bool) -> bool:
    """Question oui/non. Entrée seul reconduit `default`."""
    console.blank()
    answer = console.ask(label, "O/n" if default else "o/N").strip().lower()
    if not answer:
        return default
    return answer in _YES


def text(label: str, default: str, multiline: bool = False) -> str:
    """Saisie libre, sur une ligne ou jusqu'à une ligne vide."""
    if multiline:
        console.question(label)
        console.note("Une ligne vide pour terminer.")
        return lines() or default

    console.blank()
    return console.ask(label, default).strip() or default


def choice(label: str, options: list[Any], default: Any) -> Any:
    """Choix d'une option parmi la liste, par son numéro."""
    _list_options(label, options, retained=[default] if default is not None else [])

    chosen = _option_at(console.ask(f"Choix parmi 1-{len(options)}").strip(), options)
    if chosen is not None:
        return chosen
    return default if default is not None else (options[0] if options else "")


def multi_choice(label: str, options: list[Any], default: list[Any]) -> list[Any]:
    """
    Sélection multiple : l'utilisateur entre les numéros qui l'intéressent.

    Sans option à proposer, la question n'est pas posée — il n'y a rien à
    choisir dans ce rapport.
    """
    if not options:
        return list(default)

    # Les réponses de la dernière génération sont marquées : les reconduire d'un
    # Entrée évite de faire disparaître une partie déjà rédigée.
    _list_options(label, options, retained=default)
    console.note(
        "Numéros séparés par une virgule — "
        + ("vide = on garde les retenus ci-dessus." if default else "vide = on garde tout.")
    )
    answer = console.ask("Numéros").strip()
    if not answer:
        return list(default)

    chosen: list[Any] = []
    ignored: list[str] = []
    for piece in answer.replace(";", ",").split(","):
        number = piece.strip()
        option = _option_at(number, options)
        if option is None:
            if number:
                ignored.append(number)
        elif option not in chosen:
            chosen.append(option)

    if ignored:
        console.warn(f"Réponse ignorée : {', '.join(ignored)}")
    return chosen


def lines() -> str:
    """Lit plusieurs lignes jusqu'à une ligne vide."""
    collected: list[str] = []
    while True:
        line = console.ask("")
        if not line.strip():
            return "\n".join(collected)
        collected.append(line)


def as_list(value: Any) -> list[Any]:
    """Normalise en liste la valeur proposée à un choix multiple."""
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple, set)) else [value]


def _list_options(label: str, options: list[Any], retained: list[Any]) -> None:
    console.question(label)
    for index, option in enumerate(options, start=1):
        console.option(index, option, retained=option in retained)


def _option_at(answer: str, options: list[Any]) -> Any | None:
    """Option désignée par un numéro saisi, ou None s'il ne désigne rien."""
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        return None
    return options[int(answer) - 1]
