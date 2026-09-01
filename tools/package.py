"""
Assemble le dossier livré aux utilisateurs, puis le compresse.

    task package        construit l'exécutable, assemble, zippe

Le zip contient l'exécutable, la configuration, le template et un mode
d'emploi. La configuration et le template sont livrés en clair : c'est ainsi
que l'utilisateur adapte le document sans rien reconstruire.
"""

import os
import platform
import shutil
import sys
import tomllib
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

# Fichiers livrés à côté de l'exécutable, et modifiables par l'utilisateur.
PAYLOAD = ("config_doc_pbi.yaml", "template-doc-pbib.docx")

# Mode d'emploi joint au dossier livré.
README = "README.md"


def main() -> int:
    version = _version()
    system = platform.system().lower()
    executable = _executable()

    if executable is None:
        print("Exécutable introuvable dans dist/ — lancez d'abord `task build`.")
        return 1
    if system != "windows":
        print(
            f"Attention : construit sous {system}. Un .exe se construit sous Windows."
        )

    name = f"powerbi-doc-{version}-{system}"
    folder = os.path.join(DIST, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)

    shutil.copy2(executable, folder)
    for item in PAYLOAD:
        shutil.copy2(os.path.join(ROOT, item), folder)
    _write_readme(folder, version)

    archive = _zip(folder, os.path.join(DIST, f"{name}.zip"))

    print(f"Dossier : {os.path.relpath(folder, ROOT)}")
    print(
        f"Archive : {os.path.relpath(archive, ROOT)}  ({os.path.getsize(archive) / 1e6:.1f} Mo)"
    )
    return 0


def _version() -> str:
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        return tomllib.load(f)["project"]["version"]


def _executable() -> str | None:
    for name in ("powerbi-doc.exe", "powerbi-doc"):
        path = os.path.join(DIST, name)
        if os.path.isfile(path):
            return path
    return None


def _write_readme(folder: str, version: str) -> None:
    """Recopie le mode d'emploi en y inscrivant la version."""
    with open(os.path.join(ROOT, "tools", README), "r", encoding="utf-8") as f:
        # `replace` et non `format` : le mode d'emploi parle de la
        # configuration, où les accolades sont de mise (`{{ report.name }}`).
        # Un gabarit les prendrait pour des champs et échouerait le jour où
        # l'une d'elles y sera citée.
        text = f.read().replace("{version}", version)
    # Fins de ligne Windows : le Bloc-notes reste la visionneuse par défaut.
    with open(os.path.join(folder, README), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)


def _zip(folder: str, archive: str) -> str:
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for directory, _, files in os.walk(folder):
            for name in files:
                path = os.path.join(directory, name)
                bundle.write(path, os.path.relpath(path, os.path.dirname(folder)))
    return archive


if __name__ == "__main__":
    sys.exit(main())
