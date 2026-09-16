"""
La documentation du code, servie ou construite.

    python tools/docs.py           tout le projet, servi et rechargé à chaud
    python tools/docs.py --build   le site statique, dans docs/site/

`pdoc` est en option (`pip install -e ".[dev]"`) : il ne sert qu'au
développement.
"""

import argparse
import os
import pkgutil
import subprocess
import sys
from importlib import import_module

# Le dépôt doit être sur le chemin d'import : ce script vit dans `tools/`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ROOTS = ["main", "src.pbi_extractor", "src.report_generator", "src.core"]

DEFAULT_OUTPUT = os.path.join(ROOT, "docs", "site")
TEMPLATES = os.path.join(ROOT, "docs", "templates")


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du script"""
    args = _parse_args(argv)
    names = [name for root in ROOTS for name in _modules(root)]
    if not names:
        print("Aucun module à documenter.")
        return 1

    command = [sys.executable, "-m", "pdoc", *names, *_options(args)]
    print(f"{len(names)} module(s)")

    try:
        return subprocess.call(command, cwd=ROOT)  # noqa: S603
    except FileNotFoundError:
        print('pdoc n\'est pas installé. Lancez `pip install -e ".[dev]"`.')
        return 1


def _options(args: argparse.Namespace) -> list[str]:
    """Réglages passés à pdoc, communs aux deux modes."""
    common = [
        # Les docstrings du projet sont de la prose Markdown, avec des sections
        # `Args:` à la mode Google là où une signature mérite d'être détaillée.
        "--docformat",
        "google",
        "--template-directory",
        TEMPLATES,
    ]
    if args.build:
        return [*common, "--output-directory", args.output]
    return [*common, "--host", args.host, "--port", str(args.port)]


def _modules(root: str) -> list[str]:
    """Modules à documenter sous `root`, dans l'ordre alphabétique."""
    module = _import(root)
    if module is None:
        return []
    if not hasattr(module, "__path__"):
        # Un module seul — `main` : il n'a rien à parcourir.
        return [root]

    found = {root}
    refused = set()
    for info in pkgutil.walk_packages(module.__path__, prefix=f"{root}."):
        parts = info.name.split(".")
        if "__main__" in parts:
            continue
        if "tests" in parts:
            # Nommer le paquet de tests suffit : ses modules suivent.
            package = ".".join(parts[: parts.index("tests") + 1])
            if _reached_alone(package):
                refused.add(f"!{package}")
        elif not _reached_alone(info.name):
            found.add(info.name)

    return sorted(found) + sorted(refused)


def _reached_alone(name: str) -> bool:
    """
    Vrai si `pdoc` atteint ce module sans qu'on le lui nomme.

    Il déroule les sous-modules d'un paquet, sauf si celui-ci déclare
    `__all__` — auquel cas il s'en tient à ce qui y est nommé. Les sous-modules
    des paquets du projet doivent donc être nommés un à un, hormis ceux que
    l'`__all__` cite déjà : les nommer deux fois ferait deux fois la page.
    """
    parent = _import(".".join(name.split(".")[:-1]))
    if parent is None:
        return True

    exported = getattr(parent, "__all__", None)
    return exported is None or name.rsplit(".", maxsplit=1)[-1] in exported


def _import(name: str):
    """Importe un module, ou dit lequel manque."""
    try:
        return import_module(name)
    except ImportError as e:
        print(f"Module « {name} » introuvable : {e}")
        return None


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Lit la ligne de commande de l'outil."""
    parser = argparse.ArgumentParser(
        prog="python tools/docs.py",
        description="Sert ou construit la documentation du code (pdoc).",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Écrire le site statique au lieu de le servir",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Dossier du site (défaut : {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Adresse d'écoute")
    parser.add_argument("-p", "--port", type=int, default=8080, help="Port d'écoute")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
