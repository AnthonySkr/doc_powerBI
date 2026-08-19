"""
Pilotage de Word pour recalculer les champs du document (Windows uniquement).

Sans cela, la table des matières est simplement marquée « à recalculer » et
Word s'en charge à l'ouverture du fichier. Cette étape n'est utile que pour
obtenir un document déjà à jour sans l'ouvrir : elle exige Word installé et le
paquet `pywin32`, et reste donc optionnelle.
"""

import os


def refresh_fields(path: str) -> str:
    """Recalcule les champs du document. Retourne un message décrivant l'issue."""
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        return (
            "Word non piloté (pywin32 absent) : la table des matières sera "
            "recalculée à l'ouverture du document"
        )

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
        return "Table des matières recalculée par Word"
    except Exception as e:  # noqa: BLE001
        return f"Word n'a pas pu recalculer les champs ({e}) — mise à jour à l'ouverture"
    finally:
        try:
            if document is not None:
                document.Close(False)
            if word is not None:
                word.Quit()
        except Exception:  # noqa: BLE001, S110
            pass
