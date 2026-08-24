"""
Pose des marqueurs pendant l'écriture du document.

Le builder délègue ici deux gestes, tous deux sans effet visible :
  - ancrer un élément documenté et retenir s'il a changé (`element`) ;
  - encadrer un contenu produit par le script (`owned`), pour que la
    régénération sache qu'il peut le réécrire — et, par différence, que tout
    le reste appartient à l'utilisateur, y compris ce qui a été glissé au
    milieu : le marqueur de fermeture relève l'empreinte de chaque contenu
    écrit, ce qui permet plus tard de reconnaître les ajouts.
"""

from contextlib import contextmanager
from typing import Any

from docx.oxml.ns import qn

from src.config import DocConfig, render
from src.merge import ChangeLog, PreviousDocument, markers

_PARAGRAPH = qn("w:p")
_TABLE = qn("w:tbl")


class MergeWriter:
    def __init__(self, doc, config: DocConfig, previous: PreviousDocument | None):
        self.doc = doc
        self.previous = previous or PreviousDocument()
        self.options = config.merge
        self.enabled = bool(self.options.get("enabled", True))
        self.log = ChangeLog(is_update=self.previous.exists)

    def anchor(self, section: dict[str, Any], context: dict[str, Any]) -> None:
        """
        Ancre un élément documenté.

        L'identifiant est le `bookmark:` du plan quand il en porte un
        (`measure:Marge`, `visual:<page>:<visuel>`), sinon `section:<id>` : des
        identifiants stables, issus de Power BI ou du plan. Le `fingerprint:`
        décrit l'état technique dont dépend la documentation rédigée.
        """
        element_id = self._identifier(section, context)
        if not element_id:
            return

        digest = markers.fingerprint(render(section.get("fingerprint"), context))
        self.log.record(element_id, self.previous.status(element_id, digest))
        markers.write(self.doc, markers.element(element_id, digest))

    @contextmanager
    def owned(self, block: dict[str, Any]):
        """
        Encadre un contenu produit par le script, donc réécrit à chaque
        génération.

        Sont concernés les blocs qui n'exposent que des données du rapport :
        `property` (code DAX, sources, usages) et `table` (champs d'un visuel).
        Tout le reste — paragraphes, emplacements d'image, zones à compléter —
        est une amorce : écrite à la première génération, puis laissée à
        l'utilisateur. Le plan peut trancher explicitement avec `generated:`.
        """
        block_id = block.get("id")
        if not self.enabled or not block_id or not _is_generated(block):
            yield
            return

        opening = markers.write(self.doc, markers.generated(str(block_id)))
        try:
            yield
        finally:
            markers.write(self.doc, markers.generated_end(_digests(opening)))

    def _identifier(self, section: dict[str, Any], context: dict[str, Any]) -> str:
        if not self.enabled:
            return ""
        if section.get("bookmark"):
            return render(section["bookmark"], context)
        return f"section:{section['id']}" if section.get("id") else ""


def _digests(opening) -> list[str]:
    """
    Empreintes des contenus écrits depuis l'ouverture du bloc, dans l'ordre.

    Elles disent, à la génération suivante, ce que le script avait posé là :
    tout ce qu'on retrouvera en plus entre les deux marqueurs aura été écrit
    par l'utilisateur, et lui sera rendu (voir `merge.salvage`).
    """
    return [
        markers.digest(node)
        for node in opening._p.itersiblings()
        if node.tag in (_PARAGRAPH, _TABLE)
    ]


# Types de blocs dont le contenu n'est fait que de données du rapport.
_GENERATED_TYPES = ("property", "table")


def _is_generated(block: dict[str, Any]) -> bool:
    if "generated" in block:
        return bool(block["generated"])
    return block.get("type") in _GENERATED_TYPES
