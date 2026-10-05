"""
Détection des mentions de mesures dans les textes écrits dans le document.

Chaque fois qu'un nom de mesure apparaît dans un texte du document — libellé
d'un tableau, code DAX, description, paragraphe du plan —, il doit devenir un
lien interne vers la définition de cette mesure.

Ce module ne connaît que le texte : il découpe une chaîne en segments à lier ou
non, et l'écriture revient au générateur Word.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

Segment = tuple[str, str | None]
"""Un segment de texte : le signet vaut None pour un texte sans lien."""


@dataclass
class MeasureLinker:
    """Repère les noms de mesures dans un texte."""

    targets: dict[str, str] = field(default_factory=dict)
    """Nom de mesure → signet de sa définition."""

    known_names: Iterable[str] = field(default_factory=tuple)
    """
    Tous les noms du modèle, documentés ou non.

    Les mentions de ceux qui ne le sont pas sont comptées dans `unlinked` pour
    être signalées, faute de définition à viser.
    """

    case_sensitive: bool = False
    """False = la casse est ignorée, comme dans Power BI."""

    min_length: int = 2
    """En deçà, un nom est trop court : il se lierait à des bouts de phrase."""

    first_occurrence_only: bool = False
    """Ne lier que la première mention d'un même texte."""

    def __post_init__(self) -> None:
        """Compile, une fois pour toutes, le motif qui cherche les noms."""
        names = {name for name in self.targets if self._eligible(name)}
        names.update(name for name in self.known_names if self._eligible(name))

        self._by_key = {self._key(name): name for name in sorted(names)}
        self._pattern = _build_pattern(names, self.case_sensitive)

        self.linked = 0  # mentions transformées en lien
        self.unlinked: dict[str, int] = {}  # mesures mentionnées sans définition

    # ── API ───────────────────────────────────────────────────────
    def split(self, text: str, skip_bookmark: str | None = None) -> list[Segment]:
        """
        Découpe un texte en segments, à lier ou non.

        Args:
            text: le texte à parcourir.
            skip_bookmark: signet à ne jamais viser — c'est ainsi qu'une mesure
                ne se lie pas à elle-même depuis sa propre définition.
        """
        if not text or self._pattern is None:
            return [(text, None)] if text else []

        segments: list[Segment] = []
        already_linked: set[str] = set()
        position = 0

        for match in self._pattern.finditer(text):
            name = self._by_key.get(self._key(match.group(0)))
            if name is None:
                continue

            bookmark = self.targets.get(name)
            if bookmark is None:
                self.unlinked[name] = self.unlinked.get(name, 0) + 1
                continue
            if bookmark == skip_bookmark:
                continue
            if self.first_occurrence_only and bookmark in already_linked:
                continue

            if match.start() > position:
                segments.append((text[position : match.start()], None))
            segments.append((match.group(0), bookmark))
            already_linked.add(bookmark)
            self.linked += 1
            position = match.end()

        if position < len(text):
            segments.append((text[position:], None))

        return segments or [(text, None)]

    def has_targets(self) -> bool:
        """Y a-t-il seulement une mesure vers laquelle lier ?"""
        return bool(self.targets) and self._pattern is not None

    # ── Interne ───────────────────────────────────────────────────
    def _eligible(self, name: Any) -> bool:
        """Le nom est-il assez long pour être cherché dans un texte ?"""
        return isinstance(name, str) and len(name.strip()) >= max(1, self.min_length)

    def _key(self, name: str) -> str:
        """Forme de comparaison d'un nom."""
        return name if self.case_sensitive else name.casefold()


def _build_pattern(names: Iterable[str], case_sensitive: bool) -> re.Pattern | None:
    """
    Construit l'expression régulière repérant les noms de mesures.

    Les noms les plus longs passent en premier : « CA net » ne doit pas être
    reconnu comme « CA ». Les frontières de mot ne sont posées que là où le nom
    commence — ou finit — par un caractère de mot, pour que « % Marge » et
    « CA (N-1) » restent détectables.
    """
    alternatives = [_alternative(name) for name in sorted(set(names), key=lambda n: (-len(n), n))]
    alternatives = [alt for alt in alternatives if alt]
    if not alternatives:
        return None

    flags = re.UNICODE if case_sensitive else re.UNICODE | re.IGNORECASE
    return re.compile("|".join(alternatives), flags)


def _alternative(name: str) -> str:
    """Un nom de mesure en alternative d'expression régulière."""
    cleaned = (name or "").strip()
    if not cleaned:
        return ""

    prefix = r"(?<!\w)" if _is_word_char(cleaned[0]) else ""
    suffix = r"(?!\w)" if _is_word_char(cleaned[-1]) else ""
    return f"(?:{prefix}{re.escape(cleaned)}{suffix})"


def _is_word_char(char: str) -> bool:
    """Le caractère compte-t-il comme un caractère de mot ?"""
    return bool(re.match(r"\w", char, flags=re.UNICODE))


def collect_measures(source: Any) -> list[Any]:
    """
    Aplatit une collection du contexte en liste de mesures.

    Accepte aussi bien une liste de mesures qu'une liste de groupes
    (`model.tables_with_measures`) ou de tables exposant `.measures`.
    """
    measures: list[Any] = []
    seen: set[int] = set()

    def add(item: Any) -> None:
        """Retient une mesure, une seule fois."""
        if item is None or id(item) in seen:
            return
        seen.add(id(item))
        measures.append(item)

    def walk(value: Any) -> None:
        """Descend dans une collection jusqu'aux mesures qu'elle porte."""
        if value is None:
            return
        if isinstance(value, dict):
            value = list(value.values())
        if isinstance(value, (list, tuple, set)):
            for item in value:
                walk(item)
            return
        inner = getattr(value, "measures", None)
        if inner:
            walk(inner)
        elif hasattr(value, "name") and hasattr(value, "expression"):
            add(value)

    walk(source)
    return measures
