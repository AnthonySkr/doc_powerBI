"""
Le noyau commun aux applications.

Ce que toutes partagent, et rien de plus :

    console.py    le dialogue avec le terminal
    paths.py      la localisation des fichiers livrés (exécutable compris)
    models.py     les structures de données qui circulent entre les apps
    exchange.py   le fichier qu'elles se passent, et son codec
    config/       le plan du document (`config_doc_pbi.yaml`)

Une application peut dépendre de `shared` ; `shared` ne dépend d'aucune
application, et les applications ne dépendent pas les unes des autres.
"""
