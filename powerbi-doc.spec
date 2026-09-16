# -*- mode: python ; coding: utf-8 -*-
"""
Recette PyInstaller — construit l'exécutable distribué aux utilisateurs.

    task build          construit dist/powerbi-doc(.exe)
    task package        y ajoute la configuration et le template, et zippe

L'exécutable embarque une copie de `config.yaml` et du template, qui
sert de secours. Ce sont les fichiers livrés **à côté** de l'exe qui font foi :
c'est ainsi que l'utilisateur adapte le plan du document sans reconstruire
(voir `src/core/paths.py`).

Il embarque aussi sa version : elle vient du dernier tag du dépôt, que l'exe
n'a plus sous la main une fois distribué (voir `src/core/version.py`).
"""

import sys

from PyInstaller.utils.hooks import collect_data_files

# Le dépôt doit être sur le chemin d'import : la recette est lue par
# PyInstaller, pas par l'interpréteur du projet. `SPECPATH` est le dossier de
# ce fichier, que PyInstaller dépose dans l'espace de noms de la recette.
sys.path.insert(0, SPECPATH)

from src.core.version import write_stamp  # noqa: E402

NAME = "powerbi-doc"

# Fichiers déposés à la racine du bundle : `(source, destination)`.
DATA = [
    ("config.yaml", "."),
    ("template-doc-pbib.docx", "."),
    # La version, relevée maintenant : l'exe ne saurait pas la retrouver seul.
    (str(write_stamp(SPECPATH)), "."),
    # python-docx ouvre ses propres gabarits XML : sans eux, l'exécutable
    # échoue à la première écriture de document.
    *collect_data_files("docx"),
]

# Modules inutiles au script, écartés pour alléger l'exécutable.
EXCLUDES = ["tkinter", "test", "pydoc_data", "sqlite3", "unittest"]

analysis = Analysis(
    ["main.py"],
    pathex=["."],
    datas=DATA,
    # Tout est atteint depuis `main.py`, que PyInstaller suit.
    hiddenimports=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    name=NAME,
    console=True,  # le script dialogue avec l'utilisateur dans le terminal
    debug=False,
    strip=False,
    upx=False,
    onefile=True,
)
