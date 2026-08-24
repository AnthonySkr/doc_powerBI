"""
Recopie d'un contenu d'un document Word vers un autre.

Copier le XML ne suffit pas. Un paragraphe ne se suffit pas à lui-même : il
renvoie à des *parties* du fichier .docx qui vivent ailleurs.

    une capture d'écran, un lien externe   une relation (`r:embed`, `r:id`)
    une liste à puces ou numérotée         `numbering.xml`
    un style créé dans le document         `styles.xml`
    un commentaire de révision             `comments.xml`

Le document neuf part du template : il ne connaît rien de tout cela. Recopier
le paragraphe seul donnait donc une image cassée, une liste qui perd ses
puces, un texte qui retombe en « Normal », et — pour un commentaire — un
fichier que Word doit réparer à l'ouverture.

Ce module recopie l'élément et emmène avec lui ce dont il dépend.
"""

import copy

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn

# Espace de noms des relations : tout attribut qui en relève (`r:embed`,
# `r:id`, `r:link`) désigne une partie du document source.
_RELATIONS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_BOOKMARK_START = qn("w:bookmarkStart")
_BOOKMARK_END = qn("w:bookmarkEnd")
_ID = qn("w:id")
_VAL = qn("w:val")

_NUM_ID = qn("w:numId")
_NUM = qn("w:num")
_ABSTRACT_NUM = qn("w:abstractNum")
_ABSTRACT_NUM_ID = qn("w:abstractNumId")

_STYLE = qn("w:style")
_STYLE_ID = qn("w:styleId")
_STYLE_REFERENCES = (qn("w:pStyle"), qn("w:rStyle"), qn("w:tblStyle"))
# Styles dont un style copié dépend à son tour.
_STYLE_LINKS = (qn("w:basedOn"), qn("w:link"), qn("w:next"))

_COMMENT_REFERENCES = (
    qn("w:commentReference"),
    qn("w:commentRangeStart"),
    qn("w:commentRangeEnd"),
)


class Transplanter:
    """Recopie des éléments depuis un document source vers un document cible."""

    def __init__(self, source_document, target_document, first_bookmark_id: int = 10_000):
        self.source = source_document.part if source_document is not None else None
        self.target = target_document.part
        self._relations: dict[str, str] = {}
        self._numbering: dict[str, str] = {}
        self._styles: set[str] | None = None
        self._comments_attached = False
        self._bookmark_id = first_bookmark_id

    def copy(self, node):
        """Retourne une copie de `node` rattachée au document cible."""
        clone = copy.deepcopy(node)
        self._remap_relations(clone)
        self._renumber_bookmarks(clone)
        self._carry_styles(clone)
        self._carry_numbering(clone)
        self._carry_comments(clone)
        return clone

    # ── Relations : images, objets, liens externes ────────────────
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

    # ── Styles créés dans le document ─────────────────────────────
    def _carry_styles(self, clone) -> None:
        """
        Emmène la définition des styles que le template ne connaît pas.

        Un style créé dans le document — ou hérité d'un copier-coller — n'existe
        que dans son `styles.xml`. Sans sa définition, le texte recopié retombe
        en « Normal » et la mise en forme est perdue.
        """
        source = _part_element(self.source, RT.STYLES)
        target = _part_element(self.target, RT.STYLES)
        if source is None or target is None:
            return

        for element in clone.iter(*_STYLE_REFERENCES):
            self._carry_style(element.get(_VAL), source, target)

    def _carry_style(self, style_id: str | None, source, target, depth: int = 0) -> None:
        """Copie un style et ceux dont il dépend (`basedOn`, `link`, `next`)."""
        if self._styles is None:
            self._styles = {node.get(_STYLE_ID) for node in target.iter(_STYLE)}
        if not style_id or style_id in self._styles or depth > 10:
            return

        definition = next(
            (node for node in source.iter(_STYLE) if node.get(_STYLE_ID) == style_id), None
        )
        if definition is None:
            return

        self._styles.add(style_id)
        copied = copy.deepcopy(definition)
        target.append(copied)
        for link in copied.iter(*_STYLE_LINKS):
            self._carry_style(link.get(_VAL), source, target, depth + 1)

    # ── Listes à puces et numérotées ──────────────────────────────
    def _carry_numbering(self, clone) -> None:
        """
        Emmène la numérotation des listes recopiées.

        Presser le bouton « liste à puces » crée dans le document une instance
        de numérotation qui n'appartient qu'à lui. Le document neuf part du
        template : sans cette instance, le paragraphe garde son retrait mais
        perd sa puce ou son numéro.
        """
        source = _part_element(self.source, RT.NUMBERING)
        if source is None:
            return

        target = _part_element(self.target, RT.NUMBERING)
        if target is None:
            # Le template n'a aucune numérotation : celle du document précédent
            # peut donc être reprise telle quelle, sans risque de collision.
            self.target.relate_to(self.source.part_related_by(RT.NUMBERING), RT.NUMBERING)
            return

        for element in clone.iter(_NUM_ID):
            new_id = self._numbering_instance(element.get(_VAL), source, target)
            if new_id:
                element.set(_VAL, new_id)

    def _numbering_instance(self, num_id: str | None, source, target) -> str:
        """Recopie une instance de numérotation, et retourne son numéro dans la cible."""
        if not num_id:
            return ""
        if num_id in self._numbering:
            return self._numbering[num_id]

        instance = next((node for node in source.iter(_NUM) if node.get(_NUM_ID) == num_id), None)
        if instance is None:
            return ""

        copied = copy.deepcopy(instance)
        new_num = str(_next_id(target, _NUM, _NUM_ID))
        copied.set(_NUM_ID, new_num)

        # L'instance renvoie à une numérotation abstraite — puces, numéros,
        # retraits — qui doit suivre elle aussi.
        reference = copied.find(_ABSTRACT_NUM_ID)
        if reference is not None:
            abstract = next(
                (
                    node
                    for node in source.iter(_ABSTRACT_NUM)
                    if node.get(_ABSTRACT_NUM_ID) == reference.get(_VAL)
                ),
                None,
            )
            if abstract is not None:
                new_abstract = str(_next_id(target, _ABSTRACT_NUM, _ABSTRACT_NUM_ID))
                copied_abstract = copy.deepcopy(abstract)
                copied_abstract.set(_ABSTRACT_NUM_ID, new_abstract)
                # `w:abstractNum` précède `w:num` dans le schéma OOXML.
                _insert_abstract(target, copied_abstract)
                reference.set(_VAL, new_abstract)

        target.append(copied)
        self._numbering[num_id] = new_num
        return new_num

    # ── Commentaires de révision ──────────────────────────────────
    def _carry_comments(self, clone) -> None:
        """
        Emmène les commentaires attachés au contenu recopié.

        Une référence de commentaire sans le `comments.xml` qui la définit rend
        le fichier invalide : Word annonce un « contenu illisible » et répare.
        Le générateur n'écrit aucun commentaire — la partie du document
        précédent peut donc être reprise entière. À défaut, les références
        orphelines sont retirées : mieux vaut perdre l'annotation que le
        fichier.
        """
        references = list(clone.iter(*_COMMENT_REFERENCES))
        if not references:
            return

        if not self._comments_attached:
            self._comments_attached = _attach_comments(self.source, self.target)

        if not self._comments_attached:
            for element in references:
                _remove(element)

    def bookmark_names(self, node) -> set[str]:
        """Noms des signets portés par un élément (pour vérifier les liens)."""
        return {
            name
            for start in node.iter(_BOOKMARK_START)
            if (name := start.get(qn("w:name"))) is not None
        }


def _part_element(part, reltype: str):
    """Élément racine d'une partie liée (`styles.xml`, `numbering.xml`), ou None."""
    if part is None:
        return None
    try:
        return part.part_related_by(reltype).element
    except (KeyError, AttributeError):
        return None


def _attach_comments(source, target) -> bool:
    """Rattache au document cible la partie des commentaires du document source."""
    if source is None or _part_element(target, RT.COMMENTS) is not None:
        return _part_element(target, RT.COMMENTS) is not None
    try:
        target.relate_to(source.part_related_by(RT.COMMENTS), RT.COMMENTS)
    except (KeyError, AttributeError):
        return False
    return True


def _next_id(root, tag: str, attribute: str) -> int:
    """Premier numéro libre parmi les éléments `tag` de `root`."""
    used = {int(value) for node in root.iter(tag) if (value := node.get(attribute) or "").isdigit()}
    return max(used, default=0) + 1


def _insert_abstract(root, abstract) -> None:
    """Insère une numérotation abstraite avant la première instance `w:num`."""
    first = next(iter(root.iter(_NUM)), None)
    if first is None:
        root.append(abstract)
    else:
        first.addprevious(abstract)


def _remove(element) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)
