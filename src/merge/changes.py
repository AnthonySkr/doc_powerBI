"""Bilan des différences entre le document précédent et le rapport actuel."""

from dataclasses import dataclass, field

from src.merge.previous import CHANGED, NEW, UNCHANGED


@dataclass
class ChangeLog:
    """Ce qui a été constaté pendant la génération, affiché en fin d'exécution."""

    is_update: bool = False
    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    # Éléments retrouvés sous un autre identifiant : (identifiant d'avant,
    # identifiant d'aujourd'hui). Ni un ajout, ni un retrait.
    renamed: list[tuple[str, str]] = field(default_factory=list)
    preserved: int = 0  # contenus de l'utilisateur repris tels quels

    def __post_init__(self) -> None:
        self._status: dict[str, str] = {}

    def record(self, element_id: str, status: str) -> None:
        self._status[element_id] = status
        {NEW: self.new, CHANGED: self.changed, UNCHANGED: self.unchanged}[status].append(element_id)

    def status_of(self, element_id: str) -> str:
        return self._status.get(element_id, UNCHANGED)

    def record_rename(self, before: str, after: str) -> None:
        """L'élément existait déjà sous un autre nom : il n'est donc pas nouveau."""
        self.renamed.append((before, after))
        if after in self.new:
            self.new.remove(after)
        self._status[after] = UNCHANGED

    @property
    def renamed_ids(self) -> set[str]:
        """Identifiants d'avant, à ne pas compter comme retirés du rapport."""
        return {before for before, _ in self.renamed}

    @property
    def written_ids(self) -> set[str]:
        return set(self._status)

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.changed or self.removed or self.renamed)

    def summary(self) -> str:
        """Phrase résumant la génération, affichée en console."""
        if not self.is_update:
            return f"Première génération : {len(self.written_ids)} élément(s) documenté(s)."
        if not self.has_changes:
            return "Aucun changement depuis la version précédente du document."

        parts = []
        if self.new:
            parts.append(f"{len(self.new)} élément(s) ajouté(s)")
        if self.changed:
            parts.append(f"{len(self.changed)} élément(s) modifié(s) — à vérifier")
        if self.renamed:
            parts.append(f"{len(self.renamed)} élément(s) renommé(s)")
        if self.removed:
            parts.append(f"{len(self.removed)} élément(s) retiré(s) du rapport")
        return "Mise à jour : " + ", ".join(parts) + "."

    def details(self) -> list[str]:
        """Lignes de détail affichées sous le résumé."""
        lines = []
        for label, names in (
            ("ajouté(s)", self.new),
            ("modifié(s)", self.changed),
            ("renommé(s)", [f"{before} → {after}" for before, after in self.renamed]),
            ("retiré(s)", self.removed),
        ):
            if names:
                shown = ", ".join(names[:6])
                suffix = f" (+{len(names) - 6})" if len(names) > 6 else ""
                lines.append(f"{len(names)} {label} : {shown}{suffix}")
        if self.preserved:
            lines.append(f"{self.preserved} contenu(s) rédigé(s) repris tels quels")
        return lines
