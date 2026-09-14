"""
Lecture des valeurs déclarées dans le plan.

Le YAML est livré en clair à côté de l'exécutable, et se modifie à la main :
un gabarit `{...}` mal orthographié, un nombre écrit en toutes lettres ou un
mode inconnu sont des fautes de frappe ordinaires. Chacune doit dire laquelle
et où, plutôt que de remonter en `KeyError` devant quelqu'un qui ne fait pas
de Python.

C'est le seul rôle de ce module : traduire ce que le plan déclare en valeur
utilisable, ou en message lisible.
"""

from typing import Any

from src.apps.document.word.errors import DocumentError

# Modes de numérotation des figures, du plus courant au plus rare.
NUMBERING_MODES = ("auto", "fixed", "none")


def format_template(template: Any, key: str, **values: str) -> str:
    """
    Applique un gabarit `{...}` déclaré dans la configuration.

    `key` est le chemin du gabarit dans le YAML : c'est lui que cite le message
    d'erreur, avec la liste des champs réellement disponibles.
    """
    try:
        return str(template).format(**values)
    except (KeyError, IndexError, ValueError) as e:
        available = ", ".join(f"{{{name}}}" for name in values) or "aucun"
        raise DocumentError(
            f"`{key}` : gabarit invalide ({e}). Champs disponibles : {available}."
        ) from e


def number(value: Any, key: str, default: float, cast=float):
    """Valeur numérique déclarée dans la configuration, ou message explicite."""
    if value is None or value == "":
        return cast(default)
    try:
        return cast(value)
    except (TypeError, ValueError) as e:
        raise DocumentError(f"`{key}` : nombre attendu, reçu '{value}'.") from e


def numbering_mode(value: Any) -> str:
    """
    Mode de numérotation des figures : `auto`, `fixed` ou `none`.

    `auto` confie le numéro à un champ Word, qui le tient à jour lui-même —
    c'est le comportement voulu dans la quasi-totalité des cas. Les anciens
    plans écrivaient un booléen : `true` vaut `auto`, `false` vaut `none`.
    """
    if isinstance(value, bool) or value is None:
        return "auto" if value is not False else "none"
    mode = str(value).strip().lower()
    return mode if mode in NUMBERING_MODES else "auto"


def column_width(column: dict[str, Any]) -> float | None:
    """Largeur d'une colonne de tableau en centimètres (`width_cm`)."""
    width = column.get("width_cm")
    return number(width, "width_cm", 0, float) if width else None
