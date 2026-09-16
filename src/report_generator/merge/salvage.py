"""
Récupération de ce qui a été écrit *dans* un contenu du script.

Le script réécrit à chaque génération les données qu'il produit, mais pas ce
qu'on a glissé au milieu : une description sous le tableau d'un groupe, une
note après une valeur, une image collée dans la ligne laissée vide. Ces
contenus-là se trouvent entre `pbi::gen` et `pbi::endgen`, là où tout est
réécrit.

Pour les distinguer, le marqueur de fin retient l'empreinte de chaque
paragraphe et tableau écrits par le script (voir `merge.markers`). À la
relecture, on compare :

    empreinte retrouvée                 →  donnée du script, réécrite
    contenu en plus                     →  écrit par l'utilisateur, rendu
    contenu à la place d'une donnée     →  donnée du script remaniée à la main :
                                           le script la réécrit (c'est la
                                           sienne), et la version retouchée
                                           part en annexe plutôt qu'à la
                                           corbeille (`merge.orphans`)
    contenu là où le script laissait     →  écrit par l'utilisateur, rendu
    un paragraphe vide

Un paragraphe vide n'est pas une donnée : ce qu'on y écrit ne remplace rien et
appartient donc à l'utilisateur.

L'empreinte ne survit pas à tout : en enregistrant, Word recoupe les runs,
perd une espace, réécrit un lien en champ, et une donnée intacte passe pour
remaniée. La fusion tranche donc en dernier ressort sur le bloc neuf : ce que
le script s'apprête à réécrire à l'identique n'a pas été retouché (voir
`merge.smart`).

Chaque contenu récupéré revient avec sa place — son rang parmi les contenus du
script — pour être reposé dans son voisinage.
"""

from docx.oxml.ns import qn

from src.report_generator.merge import markers
from src.report_generator.merge.blocks import Segment

_TABLE = qn("w:tbl")


def of(segment: Segment) -> list[tuple[int, object]]:
    """
    Contenus rédigés retrouvés dans un segment du script, chacun avec sa place.

    La place est le rang, parmi les contenus du script, devant lequel le
    contenu doit être reposé.
    """
    return scan(segment)[0]


def scan(segment: Segment) -> tuple[list[tuple[int, object]], list[tuple[int, object]]]:
    """
    Départage le contenu d'un segment du script, en un seul parcours.

    Returns:
        Ce qui a été écrit **en plus**, puis les données du script
        **retouchées** à la main. Le script réécrit ces dernières — elles sont
        à lui — mais la version retouchée part en annexe plutôt qu'à la
        corbeille. Chaque contenu vient avec son rang parmi les données du
        script, de quoi le reposer à sa place.
    """
    nodes = segment.content_nodes()
    if segment.digests is None:
        return _previous_version(nodes), []

    written = list(segment.digests)
    found = _common([markers.digest(node) for node in nodes], written)

    salvaged: list[tuple[int, object]] = []
    retouched: list[tuple[int, object]] = []
    index = 0
    last = -1  # rang de la dernière donnée du script retrouvée

    while index < len(nodes):
        if index in found:
            last = found[index]
            index += 1
            continue

        # Suite de contenus que le script ne reconnaît pas, entre deux de ses
        # données : les premiers remplacent les données manquantes du passage
        # (elles ont été remaniées à la main), les suivants sont en plus.
        unknown = []
        while index < len(nodes) and index not in found:
            unknown.append(nodes[index])
            index += 1

        gap = written[last + 1 : found.get(index, len(written))]
        count = sum(1 for digest in gap if digest != markers.EMPTY)
        retouched += [(last + 1, node) for node in unknown[:count] if markers.has_content(node)]
        salvaged += [(last + 1, node) for node in unknown[count:] if markers.has_content(node)]

    return salvaged, retouched


def _previous_version(nodes: list) -> list[tuple[int, object]]:
    """
    Segment d'un document produit par une version antérieure.

    Sans empreintes, on ne sait pas ce que le script avait écrit. On récupère
    donc la seule chose sûre : ce qui suit le dernier tableau du segment, où
    le script ne laisse qu'un paragraphe vide.
    """
    tables = [rank for rank, node in enumerate(nodes) if node.tag == _TABLE]
    if not tables:
        return []
    return [
        (rank, node)
        for rank, node in enumerate(nodes)
        if rank > tables[-1] and markers.has_content(node)
    ]


def _common(found: list[str], written: list[str]) -> dict[int, int]:
    """
    Apparie les contenus relus avec ceux que le script avait écrits.

    Plus longue suite commune : elle garde l'ordre, ce qui permet de situer
    les contenus en plus — un ajout ne décale pas ce qui suit.
    """
    lengths = [[0] * (len(written) + 1) for _ in range(len(found) + 1)]
    for i in reversed(range(len(found))):
        for j in reversed(range(len(written))):
            lengths[i][j] = (
                lengths[i + 1][j + 1] + 1
                if found[i] == written[j]
                else max(lengths[i + 1][j], lengths[i][j + 1])
            )

    pairs: dict[int, int] = {}
    i = j = 0
    while i < len(found) and j < len(written):
        if found[i] == written[j]:
            pairs[i] = j
            i += 1
            j += 1
        elif lengths[i + 1][j] >= lengths[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs
