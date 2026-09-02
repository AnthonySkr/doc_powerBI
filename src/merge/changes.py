"""Bilan des différences entre le document précédent et le rapport actuel."""

from dataclasses import dataclass, field

from src.merge.previous import CHANGED, NEW, UNCHANGED


@dataclass
class ChangeLog:
    """
    Ce qui a été constaté pendant la génération, affiché en fin d'exécution.

    Rien n'est signalé dans le document lui-même : ce qui a été ajouté ou
    modifié se lit ici, par son titre, et le document reste net.
    """

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
        # Titre de chaque élément ancré : c'est lui qu'on affiche, l'identifiant
        # technique (`visual:page_ventes:v_evolution`) ne disant rien au lecteur.
        self._titles: dict[str, str] = {}

    def record(self, element_id: str, status: str, title: str = "") -> None:
        self._status[element_id] = status
        if title:
            self._titles[element_id] = title
        {NEW: self.new, CHANGED: self.changed, UNCHANGED: self.unchanged}[status].append(element_id)

    def title_of(self, element_id: str) -> str:
        """Titre d'un élément, ou son identifiant faute de titre."""
        return self._titles.get(element_id) or element_id

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
        """
        Lignes de détail affichées sous le résumé.

        Les ajouts et les modifications sont énumérés au complet, par leur
        titre : ce sont eux qu'il faut aller relire dans le document, et le
        document ne les signale plus lui-même.
        """
        lines = []
        for label, titles in (
            ("ajouté(s)", [self.title_of(name) for name in self.new]),
            ("modifié(s) — à vérifier", [self.title_of(name) for name in self.changed]),
            (
                "renommé(s)",
                [f"{before} → {self.title_of(after)}" for before, after in self.renamed],
            ),
            ("retiré(s) du rapport", self.removed),
        ):
            if titles:
                lines.append(f"{len(titles)} {label} :")
                lines.extend(f"· {title}" for title in titles)
        if self.preserved:
            lines.append(f"{self.preserved} contenu(s) rédigé(s) repris tels quels")
        return lines
