"""
Pose des marqueurs pendant l'écriture du document.

Le builder délègue ici deux gestes, tous deux sans effet visible :
  - ancrer un élément documenté et retenir s'il a changé (`anchor`) ;
  - encadrer un bloc du plan (`delimit`), pour lui donner une identité que la
    régénération saura retrouver.

Deux encadrements, selon à qui le contenu appartient une fois écrit :

    gen    contenu du script — réécrit à chaque génération (`property`, `table`)
    seed   amorce — écrite une fois, puis laissée à l'utilisateur (`paragraph`,
           `image`, `user_fill`)

Dans les deux cas le marqueur de fermeture relève l'empreinte de chaque contenu
écrit : elle dit plus tard ce que le script avait posé là, donc ce qui a été
ajouté ou rédigé depuis. C'est aussi cette identité qui permet à un bloc ajouté
au plan d'apparaître dans les éléments déjà documentés : sans elle, il était
indistinguable du contenu libre de l'utilisateur, et n'arrivait jamais.
"""

from contextlib import contextmanager
from typing import Any

from docx.oxml.ns import qn

from src import console
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
        # Identifiants déjà posés : deux ancres de même identifiant rendraient
        # la relecture ambiguë (voir `_unique`).
        self._used: dict[str, int] = {}
        # Un encadrement dans un autre casserait le découpage du document à la
        # relecture (voir `delimit`).
        self._enclosed = False

    def anchor(self, section: dict[str, Any], context: dict[str, Any], parent: str = "") -> str:
        """
        Ancre un élément documenté, et retourne son identifiant.

        L'identifiant est le `bookmark:` du plan quand il en porte un
        (`measure:Marge`, `visual:<page>:<visuel>`), sinon `section:<id>` : des
        identifiants stables, issus de Power BI ou du plan. Une section qui n'a
        ni l'un ni l'autre est repérée par son titre sous la partie qui la
        contient (`<parent>><titre>`) — faute de quoi elle n'aurait aucune
        identité, et une sous-partie ajoutée au rapport n'apparaîtrait jamais
        dans un document déjà généré.

        Le `fingerprint:` décrit l'état technique dont dépend la documentation
        rédigée.
        """
        title = render(section.get("title"), context)
        element_id = self._unique(self._identifier(section, context, parent, title), title)
        if not element_id:
            return ""

        digest = markers.fingerprint(render(section.get("fingerprint"), context))
        self.log.record(element_id, self.previous.status(element_id, digest))
        markers.write(self.doc, markers.element(element_id, digest))
        return element_id

    @contextmanager
    def delimit(self, block: dict[str, Any]):
        """
        Encadre un bloc du plan, pour lui donner une identité.

        Les blocs qui n'exposent que des données du rapport — `property` (code
        DAX, sources, usages) et `table` (champs d'un visuel) — appartiennent
        au script : ils sont réécrits à chaque génération. Tout le reste —
        paragraphes, emplacements d'image, zones à compléter — est une amorce :
        écrite à la première génération, puis laissée à l'utilisateur. Le plan
        peut trancher explicitement avec `generated:`.

        Un bloc sans `id:` n'est pas encadré : il n'a pas d'identité, et le plan
        ne pourra ni le réécrire ni le retrouver.
        """
        block_id = block.get("id")
        if not self.enabled or not block_id:
            yield
            return

        kind = markers.GENERATED if _is_generated(block) else markers.SEED

        if self._enclosed:
            # Un encadrement imbriqué produirait un marqueur de fin orphelin, et
            # le découpage perdrait le contenu du bloc extérieur. Le bloc reste
            # écrit, simplement sans identité propre.
            console.warn(
                f"Bloc '{block_id}' imbriqué dans un autre bloc encadré : il ne "
                "sera pas repéré à la régénération. Un bloc ne doit pas en "
                "contenir d'autres."
            )
            yield
            return

        opening = markers.write(self.doc, markers.opening(kind, str(block_id)))
        self._enclosed = True
        try:
            yield
        finally:
            self._enclosed = False
            markers.write(self.doc, markers.closing(kind, _digests(opening)))

    def _identifier(
        self, section: dict[str, Any], context: dict[str, Any], parent: str, title: str
    ) -> str:
        if not self.enabled:
            return ""
        if section.get("bookmark"):
            return render(section["bookmark"], context)
        if section.get("id"):
            return f"section:{section['id']}"
        return f"{parent}>{title}" if parent and title else ""

    def _unique(self, element_id: str, title: str) -> str:
        """
        Garantit qu'un identifiant n'est posé qu'une fois.

        Un `id:` de section placé dans une boucle produit le même
        `section:<id>` à chaque tour : les blocs deviendraient indistinguables
        et la rédaction reprise irait au mauvais endroit — ou nulle part.

        Les occurrences suivantes sont donc distinguées par leur titre, qui
        vient de la donnée parcourue et ne bouge donc pas si la collection est
        réordonnée. À défaut de titre, il ne reste que le rang, qui lui bouge :
        c'est un pis-aller, et le cas est signalé avec la vraie réponse — un
        `bookmark:` bâti sur la donnée parcourue.
        """
        if not element_id:
            return ""

        seen = self._used.get(element_id, 0)
        self._used[element_id] = seen + 1
        if not seen:
            return element_id

        if seen == 1:
            console.warn(
                f"Identifiant '{element_id}' posé plusieurs fois : les occurrences "
                "suivantes sont distinguées par leur titre. Donnez à cette section "
                "un `bookmark:` construit sur l'élément parcouru pour un repérage sûr."
            )

        distinct = f"{element_id}>{title}" if title else f"{element_id}#{seen + 1}"
        return distinct if distinct not in self._used else f"{element_id}#{seen + 1}"


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
        if node.tag in (_PARAGRAPH, _TABLE) and markers.of(node) is None
    ]


# Types de blocs dont le contenu n'est fait que de données du rapport.
_GENERATED_TYPES = ("property", "table")


def _is_generated(block: dict[str, Any]) -> bool:
    if "generated" in block:
        return bool(block["generated"])
    return block.get("type") in _GENERATED_TYPES
