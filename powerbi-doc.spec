# -*- mode: python ; coding: utf-8 -*-
"""
Recette PyInstaller — construit l'exécutable distribué aux utilisateurs.

    task build          construit dist/powerbi-doc(.exe)
    task package        y ajoute la configuration et le template, et zippe

L'exécutable embarque une copie de `config_doc_pbi.yaml` et du template, qui
sert de secours. Ce sont les fichiers livrés **à côté** de l'exe qui font foi :
c'est ainsi que l'utilisateur adapte le plan du document sans reconstruire
(voir `src/paths.py`).
"""

from PyInstaller.utils.hooks import collect_data_files

NAME = "powerbi-doc"

# Fichiers déposés à la racine du bundle : `(source, destination)`.
DATA = [
    ("config_doc_pbi.yaml", "."),
    ("template-doc-pbib.docx", "."),
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
