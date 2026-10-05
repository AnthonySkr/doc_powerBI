"""
Détection des mentions de mesures dans les textes écrits dans le document.

Le générateur écrit du texte provenant de sources variées : libellés du tableau
des références d'un visuel, code DAX, description, liste des sources utilisées,
paragraphes du plan. Chaque fois qu'un nom de mesure apparaît dans l'un de ces
textes, il doit devenir un lien interne vers la définition de la mesure.

Ce module ne connaît que le texte : il découpe une chaîne en segments
« texte simple » / « texte à lier », le générateur Word se charge de l'écriture.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# Un segment de texte : `bookmark` vaut None pour un texte sans lien.
Segment = tuple[str, str | None]


@dataclass
class MeasureLinker:
    """
    Repère les noms de mesures dans un texte.

    Args:
        targets: nom de mesure -> nom de signet de sa définition
        known_names: tous les noms de mesures du modèle, y compris ceux qui ne
            sont pas documentés. Les mentions correspondantes sont comptées
            (`unlinked`) afin de pouvoir les signaler, mais pas transformées
            en lien puisqu'elles n'ont pas de définition dans le document.
        case_sensitive: False = « Chiffre d'affaires » et « CHIFFRE D'AFFAIRES »
            désignent la même mesure (comportement de Power BI).
        min_length: longueur minimale d'un nom pris en compte. Évite qu'une
            mesure au nom très court ne se lie à un fragment de phrase.
        first_occurrence_only: True = seule la première mention d'une mesure
            est transformée en lien dans un même texte.
    """

    targets: dict[str, str] = field(default_factory=dict)
    known_names: Iterable[str] = field(default_factory=tuple)
    case_sensitive: bool = False
    min_length: int = 2
    first_occurrence_only: bool = False

    def __post_init__(self) -> None:
        names = {name for name in self.targets if self._eligible(name)}
        names.update(name for name in self.known_names if self._eligible(name))

        self._by_key = {self._key(name): name for name in sorted(names)}
        self._pattern = _build_pattern(names, self.case_sensitive)

        self.linked = 0  # mentions transformées en lien
        self.unlinked: dict[str, int] = {}  # mesures mentionnées sans définition

    # ── API ───────────────────────────────────────────────────────
    def split(self, text: str, skip_bookmark: str | None = None) -> list[Segment]:
        """
        Découpe `text` en segments. Les mentions de mesures reçoivent le nom du
        signet à viser, le reste du texte est retourné tel quel.

        `skip_bookmark` permet de ne pas créer de lien d'une mesure vers
        elle-même (mention de la mesure dans sa propre définition).
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
        return bool(self.targets) and self._pattern is not None

    # ── Interne ───────────────────────────────────────────────────
    def _eligible(self, name: Any) -> bool:
        return isinstance(name, str) and len(name.strip()) >= max(1, self.min_length)

    def _key(self, name: str) -> str:
        return name if self.case_sensitive else name.casefold()


def _build_pattern(names: Iterable[str], case_sensitive: bool) -> re.Pattern | None:
    """
    Construit l'expression régulière repérant les noms de mesures.

    Les noms les plus longs sont testés en premier pour qu'une mesure
    « CA net » ne soit pas reconnue comme la mesure « CA ». Les frontières de
    mot ne sont posées que du côté où le nom commence (ou finit) par un
    caractère de mot : « % Marge » ou « CA (N-1) » restent ainsi détectables.
    """
    alternatives = [_alternative(name) for name in sorted(set(names), key=lambda n: (-len(n), n))]
    alternatives = [alt for alt in alternatives if alt]
    if not alternatives:
        return None

    flags = re.UNICODE if case_sensitive else re.UNICODE | re.IGNORECASE
    return re.compile("|".join(alternatives), flags)


def _alternative(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return ""

    prefix = r"(?<!\w)" if _is_word_char(cleaned[0]) else ""
    suffix = r"(?!\w)" if _is_word_char(cleaned[-1]) else ""
    return f"(?:{prefix}{re.escape(cleaned)}{suffix})"


def _is_word_char(char: str) -> bool:
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
        if item is None or id(item) in seen:
            return
        seen.add(id(item))
        measures.append(item)

    def walk(value: Any) -> None:
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
