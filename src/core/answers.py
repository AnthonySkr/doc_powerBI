"""
Mémoire des réponses données au lancement.

Les questions de `inputs:` se reposent à chaque génération, et l'une d'elles
pèse lourd : les visuels écartés de la documentation. En oublier un le fait
réapparaître, en cocher un de plus renvoie la rédaction correspondante en
annexe — ce n'est pas une liste à confier à la mémoire de l'utilisateur.

Les réponses sont donc conservées à côté du projet et reproposées ensuite : un
Entrée les reconduit. En `--no-input`, ce sont elles qui servent, plutôt que
les valeurs figées du plan. Le fichier est en clair et se modifie à la main ;
le supprimer repart du plan.
"""

from pathlib import Path
from typing import Any

import yaml

from src.core import console
from src.core.config import DocConfig
from src.core.expressions import render

_DEFAULT_NAME = "reponses_{{ report.name }}.yaml"

_HEADER = (
    "# Réponses de la dernière génération, reproposées à la suivante.\n"
    "# Modifiable à la main ; supprimer ce fichier repart des valeurs du plan.\n"
)


def path(config: DocConfig, context: dict[str, Any], directory: str | Path) -> Path | None:
    """Fichier des réponses dans ce dossier, ou None si la mémoire est coupée."""
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
