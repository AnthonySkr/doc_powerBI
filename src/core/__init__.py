"""
Le socle commun aux deux modules de la génération.

    models.py       les structures de données qui circulent, `PowerBiMetadata`
    config.py       le plan (`config.yaml`), ses défauts, son accès
    expressions.py  les `{{ ... }}` du plan, et les conditions
    selection.py    ce que le plan retient du rapport — pages, visuels, groupes
    console.py      le dialogue avec le terminal
    questions.py    les questions élémentaires posées au terminal
    prompts.py      le questionnaire déclaré par `inputs:`
    answers.py      la mémoire des réponses d'une génération à l'autre
    paths.py        la localisation des fichiers livrés (exécutable compris)
    window.py       la fenêtre console de l'exécutable : attente et plantages
    version.py      la version du projet, lue sur le dernier tag du dépôt

`core` ne dépend ni de l'extraction ni de l'écriture ; les deux dépendent de
lui, et jamais l'une de l'autre.

La version du projet s'expose ici, et nulle part ailleurs — et vient du dernier tag `v…`
du dépôt git (voir `src.core.version`).
"""

from src.core.version import current

__version__ = current()
"""Version du projet, relevée sur le dernier tag `v…` du dépôt."""
