"""
Lecture du document généré précédemment.

On n'en extrait que deux choses, repérées par les marqueurs invisibles :
  - l'empreinte technique de chaque élément documenté, pour savoir plus tard
    ce qui a changé dans le rapport Power BI ;
  - le texte des zones rédigées par l'utilisateur, pour le reconduire.

Le document n'est jamais modifié : il est lu, puis un document neuf est écrit.
"""

import os
from dataclasses import dataclass, field

from docx import Document

from src import console
from src.merge import markers


@dataclass
class PreviousDocument:
    """Ce qui a été retenu du document précédent."""

    path: str = ""
    # identifiant d'élément -> empreinte technique au moment de sa génération
    fingerprints: dict[str, str] = field(default_factory=dict)
    # clé de zone -> paragraphes saisis par l'utilisateur
    texts: dict[str, list[str]] = field(default_factory=dict)

    @property
    def exists(self) -> bool:
        return bool(self.path)

    def status(self, element_id: str, fingerprint: str) -> str:
        """Compare un élément du rapport actuel à ce que contenait le document."""
        if not self.exists:
            return UNCHANGED
        previous = self.fingerprints.get(element_id)
        if previous is None:
            return NEW
        if fingerprint and previous != fingerprint:
            return CHANGED
        return UNCHANGED

    def text_for(self, key: str) -> list[str]:
        """Paragraphes saisis par l'utilisateur dans cette zone, s'il y en a."""
        return self.texts.get(key, [])

    def removed(self, written_ids: set[str]) -> list[str]:
        """Éléments présents dans le document précédent mais plus dans le rapport."""
        return sorted(set(self.fingerprints) - written_ids)


# États d'un élément vis-à-vis du document précédent.
NEW = "new"
CHANGED = "changed"
UNCHANGED = "unchanged"


def read(path: str, ignored_texts: tuple[str, ...] = ()) -> PreviousDocument:
    """
    Lit le document précédent, s'il existe et porte des marqueurs.

    Args:
        path: chemin du .docx généré lors d'une exécution antérieure
        ignored_texts: textes à considérer comme « zone non remplie »
            (le texte repère `[À compléter]`), donc sans rien à reconduire.
    """
    if not os.path.isfile(path):
        return PreviousDocument()

    try:
        doc = Document(path)
    except Exception as e:  # noqa: BLE001
        console.warn(f"Document précédent illisible, il sera remplacé ({e})")
        return PreviousDocument()

    previous = PreviousDocument(path=path)
    ignored = {text.strip() for text in ignored_texts if text}
    current_slot: str | None = None
    collected: list[str] = []

    for paragraph in doc.paragraphs:
        marker = markers.parse(paragraph.text)

        if marker is None:
            if current_slot is not None:
                collected.append(paragraph.text)
            continue

        if markers.is_element(marker):
            previous.fingerprints[marker.value] = marker.fingerprint
        elif markers.is_slot(marker):
            current_slot = marker.value
            collected = []
        elif markers.is_slot_end(marker) and current_slot is not None:
            previous.texts[current_slot] = _clean(collected, ignored)
            current_slot = None

    if not previous.fingerprints and not previous.texts:
        console.info("Document précédent sans marqueurs : il sera entièrement régénéré")
        return PreviousDocument()

    written = sum(1 for texts in previous.texts.values() if texts)
    console.info(
        f"Document précédent lu : {len(previous.fingerprints)} élément(s) repéré(s), "
        f"{written} zone(s) de texte"
    )
    return previous


def _clean(paragraphs: list[str], ignored: set[str]) -> list[str]:
    """Retire les lignes vides d'encadrement et les textes repères non remplis."""
    kept = [text for text in paragraphs if text.strip() and text.strip() not in ignored]
    return kept
