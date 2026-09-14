"""
Mémoire des réponses données au lancement.

Les questions de `inputs:` se reposent à chaque génération. Certaines n'ont
pas de conséquence — le titre de l'en-tête. Une autre en a une lourde : les
visuels qu'on écarte de la documentation. Oublier d'en re-cocher un le fait
réapparaître, en cocher un de plus fait disparaître la partie correspondante,
et la rédaction qui allait avec part en annexe.

Les réponses sont donc conservées à côté du projet, et proposées par défaut à
la génération suivante : on valide en pressant Entrée. En mode `--no-input`, ce
sont elles qui servent, plutôt que les valeurs figées du YAML.

Le fichier est en clair et se modifie à la main ; le supprimer revient à
repartir des valeurs du plan.
"""

from pathlib import Path
from typing import Any

import yaml

from core import console
from core.config import DocConfig
from core.expressions import render

__all__ = ["path", "read", "write"]

_DEFAULT_NAME = "reponses_{{ report.name }}.yaml"

_HEADER = (
    "# Réponses de la dernière génération, reproposées à la suivante.\n"
    "# Modifiable à la main ; supprimer ce fichier repart des valeurs du plan.\n"
)


def path(config: DocConfig, context: dict[str, Any], directory: str | Path) -> Path | None:
    """Emplacement du fichier des réponses, ou None si la mémoire est désactivée."""
    document = config.document
    if not document.get("remember_answers", True):
        return None

    name = render(document.get("answers_file") or _DEFAULT_NAME, context)
    return Path(directory) / name if name else None


def read(answers_path: Path | None) -> dict[str, Any]:
    """Réponses de la génération précédente, ou {} s'il n'y en a pas."""
    if not answers_path or not answers_path.is_file():
        return {}

    try:
        remembered = yaml.safe_load(answers_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        console.warn(f"Réponses précédentes illisibles, elles seront ignorées ({e})")
        return {}

    if not isinstance(remembered, dict):
        return {}

    console.done(f"réponses précédentes reprises de {answers_path.name}")
    return remembered


def write(answers_path: Path | None, answers: dict[str, Any]) -> None:
    """Conserve les réponses pour la prochaine génération."""
    if not answers_path or not answers:
        return

    try:
        answers_path.parent.mkdir(parents=True, exist_ok=True)
        with answers_path.open("w", encoding="utf-8") as f:
            f.write(_HEADER)
            yaml.safe_dump(answers, f, allow_unicode=True, sort_keys=False)
    except (OSError, yaml.YAMLError) as e:
        # Ne pas perdre une génération réussie pour une mémoire d'appoint.
        console.warn(f"Réponses non conservées ({e})")
