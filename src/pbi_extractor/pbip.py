"""Localisation des dossiers d'un projet Power BI `.pbip`."""

from dataclasses import dataclass
from pathlib import Path

# Un fichier `Rapport.pbip` est accompagné des dossiers `Rapport.SemanticModel`
# (ou `Rapport.Dataset` pour les projets antérieurs) et `Rapport.Report`.
_SEMANTIC_SUFFIXES = (".SemanticModel", ".Dataset")
_REPORT_SUFFIX = ".Report"


@dataclass(frozen=True)
class PbipProject:
    """Les dossiers d'un projet `.pbip`, une fois localisés."""

    path: Path
    """Le fichier `.pbip` lui-même."""

    name: str
    """Son nom sans extension, que portent aussi les deux dossiers."""

    directory: Path
    """Le dossier qui contient le tout."""

    semantic_model_dir: Path | None
    """`<nom>.SemanticModel`, ou None s'il manque."""

    report_dir: Path | None
    """`<nom>.Report`, ou None s'il manque."""

    @classmethod
    def at(cls, pbip_path: str | Path) -> PbipProject:
        """Localise les dossiers d'un projet à partir de son fichier `.pbip`."""
        path = Path(pbip_path).expanduser().resolve()
        directory = path.parent
        name = path.stem
        return cls(
            path=path,
            name=name,
            directory=directory,
            semantic_model_dir=_first_dir(directory, name, _SEMANTIC_SUFFIXES),
            report_dir=_first_dir(directory, name, (_REPORT_SUFFIX,)),
        )

    def missing(self) -> str | None:
        """Message d'erreur si un dossier indispensable est absent, sinon None."""
        if not self.semantic_model_dir:
            return f"Dossier SemanticModel introuvable pour '{self.name}'"
        if not self.report_dir:
            return f"Dossier Report introuvable pour '{self.name}'"
        return None

    def output_dir(self, sub_directory: str | Path) -> Path:
        """Dossier de sortie, créé au besoin, à côté du fichier `.pbip`."""
        path = self.directory / sub_directory
        path.mkdir(parents=True, exist_ok=True)
        return path


def _first_dir(directory: Path, name: str, suffixes: tuple[str, ...]) -> Path | None:
    """Premier dossier `<name><suffixe>` qui existe, ou None."""
    for suffix in suffixes:
        candidate = directory / f"{name}{suffix}"
        if candidate.is_dir():
            return candidate
    return None
