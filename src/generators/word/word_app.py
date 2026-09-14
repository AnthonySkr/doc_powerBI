"""
Pilotage de Word pour recalculer les champs du document (Windows uniquement).

Sans cela, la table des matières est simplement marquée « à recalculer » et
Word s'en charge à l'ouverture du fichier. Cette étape n'est utile que pour
obtenir un document déjà à jour sans l'ouvrir : elle exige Word installé et le
paquet `pywin32`, et reste donc optionnelle.
"""

import os
from contextlib import suppress

try:
    import win32com.client  # type: ignore[import-not-found]
except ImportError:
    # Absent hors Windows, et sur un poste où `pywin32` n'est pas installé :
    # le document reste correct, Word recalculera à l'ouverture.
    win32com = None

_ABSENT = (
    "Word non piloté (pywin32 absent) : la table des matières sera "
    "recalculée à l'ouverture du document"
)


def refresh_fields(path: str) -> str:
    """Recalcule les champs du document. Retourne un message décrivant l'issue."""
    if win32com is None:
        return _ABSENT

    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        document = word.Documents.Open(os.path.abspath(path))
        document.Fields.Update()
        for toc in document.TablesOfContents:
            toc.Update()
        document.Save()
    except Exception as e:  # noqa: BLE001
        # Étape facultative pilotant une application hors du processus : Word
        # absent, occupé, ou en erreur COM. Aucune de ces issues ne doit
        # emporter une génération qui, elle, a réussi — le document est déjà
        # enregistré et reste lisible.
        return f"Word n'a pas pu recalculer les champs ({e}) — mise à jour à l'ouverture"
    else:
        return "Table des matières recalculée par Word"
    finally:
        # La fermeture est elle aussi facultative : au pire, une instance de
        # Word invisible survit à la génération.
        with suppress(Exception):
            if document is not None:
                document.Close(False)
            if word is not None:
                word.Quit()
