"""
Lecture des valeurs déclarées dans le plan.

Le YAML est livré en clair et se modifie à la main : un gabarit `{...}` mal
orthographié ou un nombre écrit en toutes lettres sont des fautes ordinaires.
Chacune doit dire laquelle et où, plutôt que de remonter en `KeyError` devant
quelqu'un qui ne fait pas de Python.

C'est tout le rôle de ce module : traduire ce que le plan déclare en valeur
utilisable, ou en message lisible.
"""

from typing import Any

from src.report_generator.word.errors import DocumentError

# Modes de numérotation des figures, du plus courant au plus rare.
NUMBERING_MODES = ("auto", "fixed", "none")


def format_template(template: Any, key: str, **values: str) -> str:
    """
    Applique un gabarit `{...}` déclaré dans le plan.

    Args:
        template: le gabarit tel qu'il est écrit dans le YAML.
        key: son chemin dans le plan, cité par le message d'erreur.
        **values: les champs que le gabarit peut citer.
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

    `auto` confie le numéro à un champ Word, qui le tient à jour lui-même.
    Les anciens plans écrivaient un booléen : `true` vaut `auto`, `false`
    vaut `none`.
    """
    if isinstance(value, bool) or value is None:
        return "auto" if value is not False else "none"
    mode = str(value).strip().lower()
    return mode if mode in NUMBERING_MODES else "auto"


def column_width(column: dict[str, Any]) -> float | None:
    """Largeur d'une colonne de tableau en centimètres (`width_cm`)."""
    width = column.get("width_cm")
    return number(width, "width_cm", 0, float) if width else None
