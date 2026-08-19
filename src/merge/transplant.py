"""
Recopie d'un contenu d'un document Word vers un autre.

Copier le XML ne suffit pas : une capture d'écran collée par l'utilisateur, un
lien externe ou un objet incorporé ne sont pas dans le paragraphe mais dans une
*partie* du fichier .docx, désignée par un identifiant de relation. Recopier le
paragraphe sans sa relation donnerait une image cassée.

Ce module recopie l'élément et emmène avec lui ce dont il dépend.
"""

import copy

from docx.oxml.ns import qn

# Espace de noms des relations : tout attribut qui en relève (`r:embed`,
# `r:id`, `r:link`) désigne une partie du document source.
_RELATIONS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_BOOKMARK_START = qn("w:bookmarkStart")
_BOOKMARK_END = qn("w:bookmarkEnd")
_ID = qn("w:id")


class Transplanter:
    """Recopie des éléments depuis un document source vers un document cible."""

    def __init__(self, source_document, target_document, first_bookmark_id: int = 10_000):
        self.source = source_document.part if source_document is not None else None
        self.target = target_document.part
        self._relations: dict[str, str] = {}
        self._bookmark_id = first_bookmark_id

    def copy(self, node):
        """Retourne une copie de `node` rattachée au document cible."""
        clone = copy.deepcopy(node)
        self._remap_relations(clone)
        self._renumber_bookmarks(clone)
        return clone

    def _remap_relations(self, clone) -> None:
        if self.source is None:
            return

        for element in clone.iter():
            for name, value in list(element.attrib.items()):
                if not name.startswith(f"{{{_RELATIONS}}}"):
                    continue
                new_id = self._relation(value)
                if new_id:
                    element.set(name, new_id)

    def _relation(self, relation_id: str) -> str:
        """Rattache au document cible la partie désignée, et retourne son nouvel id."""
        if relation_id in self._relations:
            return self._relations[relation_id]

        relation = self.source.rels.get(relation_id)
        if relation is None:
            return ""

        if relation.is_external:
            new_id = self.target.relate_to(relation.target_ref, relation.reltype, is_external=True)
        else:
            new_id = self.target.relate_to(relation.target_part, relation.reltype)

        self._relations[relation_id] = new_id
        return new_id

    def _renumber_bookmarks(self, clone) -> None:
        """
        Renumérote les signets recopiés.

        Les numéros du document source recommencent à zéro : sans cela, un
        signet recopié entrerait en collision avec ceux que le générateur vient
        de poser, et Word ouvrirait un document incohérent.
        """
        renumbered: dict[str, str] = {}

        for element in clone.iter(_BOOKMARK_START, _BOOKMARK_END):
            old = element.get(_ID)
            if old is None:
                continue
            if old not in renumbered:
                self._bookmark_id += 1
                renumbered[old] = str(self._bookmark_id)
            element.set(_ID, renumbered[old])

    def bookmark_names(self, node) -> set[str]:
        """Noms des signets portés par un élément (pour vérifier les liens)."""
        return {
            name
            for start in node.iter(_BOOKMARK_START)
            if (name := start.get(qn("w:name"))) is not None
        }
