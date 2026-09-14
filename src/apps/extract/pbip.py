"""Localisation des dossiers d'un projet Power BI `.pbip`."""

import os

# Un fichier `Rapport.pbip` est accompagné des dossiers `Rapport.SemanticModel`
# (ou `Rapport.Dataset` pour les projets antérieurs) et `Rapport.Report`.
_SEMANTIC_SUFFIXES = (".SemanticModel", ".Dataset")
_REPORT_SUFFIX = ".Report"


class PbipProject:
    """Les dossiers d'un projet .pbip, une fois localisés."""

    def __init__(self, pbip_path: str):
        self.path = os.path.abspath(pbip_path)
        self.name = os.path.splitext(os.path.basename(self.path))[0]
        self.directory = os.path.dirname(self.path)

        self.semantic_model_dir = self._find(_SEMANTIC_SUFFIXES)
        self.report_dir = self._find((_REPORT_SUFFIX,))

    def _find(self, suffixes: tuple[str, ...]) -> str | None:
        for suffix in suffixes:
            candidate = os.path.join(self.directory, f"{self.name}{suffix}")
            if os.path.isdir(candidate):
                return candidate
        return None

    def missing(self) -> str | None:
        """Message d'erreur si un dossier indispensable est absent, sinon None."""
        if not self.semantic_model_dir:
            return f"Dossier SemanticModel introuvable pour '{self.name}'"
        if not self.report_dir:
            return f"Dossier Report introuvable pour '{self.name}'"
        return None

    def output_dir(self, sub_directory: str) -> str:
        """Dossier de sortie, créé au besoin, à côté du fichier .pbip."""
        path = os.path.join(self.directory, sub_directory)
        os.makedirs(path, exist_ok=True)
        return path
