"""
Annexe des contenus qui n'ont pas retrouvé leur place.

Le principe de la fusion est de reposer chaque contenu rédigé là où il était.
Il reste des cas où c'est impossible : l'élément a disparu du rapport, le bloc
du plan n'existe plus, ou la donnée du script sur laquelle on avait écrit a été
remaniée. Jusqu'ici ces contenus étaient simplement absents du document neuf —
une perte silencieuse, que seule l'archive de `.versions/` rattrapait.

Ils sont désormais rassemblés en fin de document, sous un titre, avec la
provenance de chacun :

    Contenu non replacé
      Retiré du rapport — measure:Ancienne marge
        <ce que l'utilisateur avait écrit là>

Rien n'est jeté : l'utilisateur décide de reprendre, de déplacer ou de
supprimer. L'annexe se reconduit d'une génération à l'autre tant qu'elle n'est
pas vidée à la main, et disparaît d'elle-même une fois vide.
"""

from dataclasses import dataclass, field
from typing import Any

from src import console
from src.merge import markers
from src.merge.blocks import Block

# Identifiant de l'ancre de l'annexe, et du bloc qui porte son titre.
ELEMENT_ID = "merge:orphans"
_HEADING_BLOCK = "orphans:heading"

_DEFAULT_TITLE = "Contenu non replacé"
_DEFAULT_INTRO = (
    "Ces contenus ont été rédigés dans une version précédente de ce document, "
    "à un endroit qui n'existe plus. Ils sont rassemblés ici pour ne pas être "
    "perdus : reprenez-les où vous le souhaitez, puis supprimez cette partie."
)

_REASONS = {
    "removed": "Retiré du rapport",
    "dropped": "Bloc retiré du plan",
    "reworked": "Donnée du script retouchée à la main",
    "preamble": "Écrit avant la première partie documentée",
}


@dataclass
class Group:
    """Un lot de contenus de même provenance."""

    reason: str
    source: str
    nodes: list = field(default_factory=list)

    @property
    def label(self) -> str:
        prefix = _REASONS.get(self.reason, self.reason)
        return f"{prefix} — {self.source}" if self.source else prefix


@dataclass
class Collector:
    """Rassemble, pendant la fusion, ce qui n'a pas pu être replacé."""

    settings: dict[str, Any] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", True))

    @property
    def title(self) -> str:
        return str(self.settings.get("title") or _DEFAULT_TITLE)

    @property
    def count(self) -> int:
        return sum(len(group.nodes) for group in self.groups)

    def add(self, reason: str, source: str, nodes: list) -> None:
        """Recueille des contenus, sans les marqueurs qui les entouraient."""
        kept = [node for node in nodes if markers.of(node) is None]
        if self.enabled and kept:
            self.groups.append(Group(reason=reason, source=source, nodes=kept))


def collector(merge_options: dict[str, Any]) -> Collector:
    return Collector(settings=merge_options.get("orphans") or {})


def carried(old: dict[str, Block]) -> list:
    """
    Contenu de l'annexe du document précédent, sans son titre.

    Le titre et le texte d'explication sont réécrits à chaque fois : seuls les
    lots déjà rassemblés sont repris, pour qu'une annexe non vidée ne perde
    rien de ce qu'elle avait recueilli.
    """
    block = old.get(ELEMENT_ID)
    return block.free_after().get(_HEADING_BLOCK, []) if block is not None else []


def render(document, transplanter, styles, collector: Collector, previous: list) -> list:
    """
    Écrit l'annexe et retourne ses éléments, prêts à rejoindre le corps.

    Retourne une liste vide quand il n'y a rien à recueillir : l'annexe ne
    s'écrit que si elle a quelque chose à dire, et disparaît une fois vidée.
    """
    if not collector.enabled or (not collector.groups and not previous):
        return []

    intro = collector.settings.get("intro") or _DEFAULT_INTRO
    nodes = [markers.write(document, markers.element(ELEMENT_ID, ""))._p]

    nodes.append(markers.write(document, markers.opening(markers.SEED, _HEADING_BLOCK))._p)
    nodes.append(_paragraph(document, styles, "heading_1", collector.title))
    nodes.append(_paragraph(document, styles, "normal", intro))
    nodes.append(markers.write(document, markers.closing(markers.SEED))._p)

    nodes += [transplanter.copy(node) for node in previous]

    for group in collector.groups:
        nodes.append(_paragraph(document, styles, "todo", group.label))
        nodes += [transplanter.copy(node) for node in group.nodes]

    return nodes


def report(collector: Collector) -> None:
    """Dit en console ce qui a été recueilli, et où le retrouver."""
    if not collector.groups:
        return
    console.warn(
        f"{collector.count} contenu(s) rédigé(s) n'ont pas retrouvé leur place : "
        f"rassemblés en fin de document sous « {collector.title} »"
    )
    for group in collector.groups:
        console.detail(f"{group.label} : {len(group.nodes)} contenu(s)")


def _paragraph(document, styles, style_key: str, text: str):
    paragraph = document.add_paragraph(text, style=styles.paragraph(style_key))
    return paragraph._p
