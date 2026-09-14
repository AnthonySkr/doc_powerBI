"""
Le socle commun aux trois modules de la génération.

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

`core` ne dépend d'aucun des trois modules ; les trois dépendent de lui, et
jamais les uns des autres. La version du projet est déclarée ici, et nulle part
ailleurs : `pyproject.toml` la lit depuis ce module, l'outil de distribution
l'emploie pour nommer l'archive, et le bandeau du script l'affiche. Un
exécutable n'embarque pas les métadonnées de son paquet — sans cette constante,
il serait le seul à ne pas savoir quelle version il est.
"""

__version__ = "2.0.0"
