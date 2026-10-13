# -*- mode: python ; coding: utf-8 -*-
"""
Recette PyInstaller — construit l'exécutable distribué aux utilisateurs.

    task build          construit dist/powerbi-doc(.exe)
    task package        y ajoute la configuration et le template, et zippe

L'exécutable embarque une copie de `config.yaml` et du template, qui
sert de secours. Ce sont les fichiers livrés **à côté** de l'exe qui font foi :
c'est ainsi que l'utilisateur adapte le plan du document sans reconstruire
(voir `src/core/paths.py`).
"""

import importlib.util
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

NAME = "powerbi-doc"

# Outils de capture (extra `capture`). Le script les charge à la demande, au
# moment de photographier : rien ne casse à la construction s'ils manquent,
# et l'exécutable livré annonce seulement, chez l'utilisateur, « Capture
# indisponible ». Leur absence arrête donc la construction, ici, sous Windows
# — le seul système où un exécutable se livre.
CAPTURE = ["mss", "pywinauto"] if sys.platform == "win32" else ["mss"]

missing = [name for name in CAPTURE if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit(
        f"Outils de capture absents de l'environnement : {', '.join(missing)}.\n"
        'Installez-les avant de construire : pip install -e ".[dev,capture]"'
    )


def _submodules(package: str) -> list[str]:
    """Tous les modules d'un paquet, ses tests exceptés."""
    return collect_submodules(package, filter=lambda name: ".test" not in name)


# `pywinauto` passe par `comtypes`, qui génère et charge l'interface
# d'UI Automation à l'exécution ; `mss` choisit son module d'après le système.
# Ces chargements dynamiques échappent en partie à l'analyse : on embarque
# les paquets entiers.
HIDDEN = [module for name in CAPTURE for module in _submodules(name)]
if sys.platform == "win32":
    HIDDEN += _submodules("comtypes")

# Fichiers déposés à la racine du bundle : `(source, destination)`.
DATA = [
    ("config.yaml", "."),
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
    # Tout le reste est atteint depuis `main.py`, que PyInstaller suit.
    hiddenimports=HIDDEN,
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
