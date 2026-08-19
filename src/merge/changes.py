"""Bilan des différences entre le document précédent et le rapport actuel."""

from dataclasses import dataclass, field

from src.merge.previous import CHANGED, NEW, UNCHANGED


@dataclass
class ChangeLog:
    """Ce qui a été constaté pendant l'écriture du document."""

    is_update: bool = False
    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    restored: int = 0  # zones dont le texte utilisateur a été repris

    def record(self, element_id: str, status: str) -> None:
        {NEW: self.new, CHANGED: self.changed, UNCHANGED: self.unchanged}[status].append(element_id)

    @property
    def written_ids(self) -> set[str]:
        return set(self.new) | set(self.changed) | set(self.unchanged)

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.changed or self.removed)

    def summary(self) -> str:
        """Phrase résumant la mise à jour, écrite dans le document et la console."""
        if not self.is_update:
            return f"Première génération : {len(self.unchanged) + len(self.new)} élément(s) documenté(s)."

        if not self.has_changes:
            return "Aucun changement depuis la version précédente du document."

        parts = []
        if self.new:
            parts.append(f"{len(self.new)} élément(s) ajouté(s)")
        if self.changed:
            parts.append(f"{len(self.changed)} élément(s) modifié(s) — à vérifier")
        if self.removed:
            parts.append(f"{len(self.removed)} élément(s) retiré(s) du rapport")
        return "Mise à jour : " + ", ".join(parts) + "."

    def details(self) -> list[str]:
        """Lignes de détail affichées en console."""
        lines = []
        for label, names in (
            ("ajouté(s)", self.new),
            ("modifié(s)", self.changed),
            ("retiré(s)", self.removed),
        ):
            if names:
                shown = ", ".join(names[:6])
                suffix = f" (+{len(names) - 6})" if len(names) > 6 else ""
                lines.append(f"{len(names)} {label} : {shown}{suffix}")
        if self.restored:
            lines.append(f"{self.restored} zone(s) de texte reprises du document précédent")
        return lines
