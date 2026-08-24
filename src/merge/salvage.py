"""
Récupération de ce que l'utilisateur a écrit *à l'intérieur* d'un contenu du
script.

Le script est propriétaire des données qu'il produit — il les réécrit à chaque
génération — mais pas de ce qu'on a pu glisser au milieu : une description sous
le tableau d'un groupe, une note après une valeur, une capture collée dans la
ligne laissée vide. Ces contenus-là se trouvent entre `pbi::gen` et
`pbi::endgen`, là où la fusion réécrit tout.

Pour les distinguer, le marqueur de fin retient l'empreinte de chaque
paragraphe et tableau écrits par le script (voir `merge.markers`). À la
relecture, on compare :

    empreinte retrouvée                 →  donnée du script, réécrite
    contenu en plus                     →  écrit par l'utilisateur, rendu
    contenu à la place d'une donnée     →  donnée du script remaniée à la main :
                                           le script la réécrit (c'est la sienne)
    contenu là où le script laissait     →  écrit par l'utilisateur, rendu
    un paragraphe vide

Un paragraphe vide n'est pas une donnée : ce qu'on y écrit ne remplace rien et
appartient donc à l'utilisateur.

Chaque contenu récupéré revient avec sa place — le rang qu'il occupait parmi
les contenus du script — pour être reposé au même endroit : les données
techniques restent où elles sont, le reste retrouve son voisinage.
"""

from docx.oxml.ns import qn

from src.merge import markers
from src.merge.blocks import Segment

_TABLE = qn("w:tbl")
_TEXT = qn("w:t")

# Empreinte d'un contenu sans texte ni image : la place laissée libre par le
# script en fin de bloc.
_EMPTY = markers.fingerprint("")


def of(segment: Segment) -> list[tuple[int, object]]:
    """
    Contenus rédigés retrouvés dans un segment du script, chacun avec sa place.

    La place est le rang, parmi les contenus du script, devant lequel le
    contenu doit être reposé.
    """
    nodes = segment.content_nodes()
    if segment.digests is None:
        return _previous_version(nodes)

    written = list(segment.digests)
    found = _common([markers.digest(node) for node in nodes], written)

    salvaged: list[tuple[int, object]] = []
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
        reworked = sum(1 for digest in gap if digest != _EMPTY)
        salvaged += [(last + 1, node) for node in unknown[reworked:] if _has_content(node)]

    return salvaged


def _previous_version(nodes: list) -> list[tuple[int, object]]:
    """
    Segment d'un document produit par une version antérieure : sans empreintes,
    on ne sait pas ce que le script avait écrit.

    On récupère alors la seule chose dont on soit sûr : ce qui suit le dernier
    tableau du segment. Le script n'y laisse qu'un paragraphe vide — tout ce
    qu'on y trouve d'écrit vient donc de l'utilisateur.
    """
    tables = [rank for rank, node in enumerate(nodes) if node.tag == _TABLE]
    if not tables:
        return []
    return [
        (rank, node) for rank, node in enumerate(nodes) if rank > tables[-1] and _has_content(node)
    ]


def _common(found: list[str], written: list[str]) -> dict[int, int]:
    """
    Appariement des contenus relus avec ceux que le script avait écrits.

    Plus longue suite commune : elle conserve l'ordre, ce qui permet ensuite de
    situer les contenus en plus (un ajout ne décale pas ce qui suit).
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


def _has_content(node) -> bool:
    """Y a-t-il quelque chose à sauver : du texte, une image, un tableau ?"""
    if node.tag == _TABLE:
        return True
    text = "".join(run.text or "" for run in node.iter(_TEXT))
    return bool(text.strip()) or markers.has_picture(node)
