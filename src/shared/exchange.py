"""
Le fichier que les applications se passent.

Chaque application lit un fichier d'échange, l'enrichit, en écrit un nouveau, et
**supprime celui qu'elle a consommé**. La chaîne est donc un tapis roulant :

    extract    .pbip                  ──►  1-rapport.json
    capture    1-rapport.json         ──►  2-captures.json  (+ les PNG)
    document   2-captures.json        ──►  le .docx

À aucun moment deux applications ne sont dans la même mémoire : ce qui passe de
l'une à l'autre est ce fichier, et rien d'autre. Il s'ouvre dans un éditeur, se
compare d'une exécution à l'autre, se retouche à la main pour éprouver l'étape
suivante sans rejouer la précédente.

    Le format est du JSON indenté, clés et collections triées : deux exécutions
    sur le même rapport donnent deux fichiers identiques, et `diff` dit ce qui a
    bougé dans le rapport.

Le codec est générique : il suit les annotations des dataclasses de
`shared.models`. Un champ ajouté là-bas traverse la chaîne sans que rien ne soit
à écrire ici — c'est pourquoi ces annotations sont précises (`list[Visual]`, et
non `list`).
"""

import json
import os
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, get_args, get_origin, get_type_hints

from src.shared.models import PowerBIReport

__all__ = ["DEFAULT_DIRECTORY", "Exchange", "ExchangeError", "consume", "read", "write"]

# Version du format. Un fichier écrit par une autre version n'est pas relu au
# hasard : mieux vaut relancer l'extraction que documenter des données qu'on ne
# sait pas interpréter.
FORMAT_VERSION = 1

DEFAULT_DIRECTORY = ".echange"


class ExchangeError(Exception):
    """Le fichier d'échange est absent, illisible ou d'une autre version."""


@dataclass
class Exchange:
    """
    Ce qui circule d'une application à la suivante.

    `report` grossit au fil de la chaîne : l'extraction le remplit, la capture
    y ajoute l'inventaire de ses images, le document s'en sert et n'écrit plus
    rien. Les étapes suivantes n'ont donc jamais à remonter à la source.
    """

    report: PowerBIReport
    # Captures prises, par page puis par prise : {page: {prise: chemin}}. Les
    # chemins sont relatifs au dossier du projet, pour qu'un projet déplacé ne
    # perde pas ses images.
    captures: dict[str, dict[str, str]] = field(default_factory=dict)
    # D'où viennent ces données, et qui les a écrites — pour se repérer en
    # ouvrant le fichier.
    source: str = ""
    produced_by: str = ""
    version: int = FORMAT_VERSION

    def capture_of(self, page: str, shot: str) -> str:
        """Chemin de la capture d'une prise, ou chaîne vide s'il n'y en a pas."""
        return (self.captures.get(page) or {}).get(shot, "")


# ─────────────────────────────────────────────────────────────
#  Lecture / écriture
# ─────────────────────────────────────────────────────────────


def write(exchange: Exchange, path: str) -> str:
    """Écrit le fichier d'échange et retourne son chemin."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(encode(exchange), f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return path


def read(path: str) -> Exchange:
    """Lit un fichier d'échange, sans le supprimer."""
    if not os.path.isfile(path):
        raise ExchangeError(
            f"Fichier d'échange introuvable : '{path}'. "
            "L'étape précédente n'a pas tourné, ou son fichier a été effacé."
        )

    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ExchangeError(f"Fichier d'échange illisible ('{path}') : {e}") from e

    if not isinstance(raw, dict):
        raise ExchangeError(f"Fichier d'échange invalide ('{path}') : un objet est attendu.")

    found = raw.get("version")
    if found != FORMAT_VERSION:
        raise ExchangeError(
            f"Fichier d'échange en version {found}, attendue {FORMAT_VERSION} ('{path}'). "
            "Relancez l'extraction."
        )

    return decode(Exchange, raw)


def consume(path: str) -> Exchange:
    """
    Lit un fichier d'échange **et le supprime**.

    C'est le geste normal d'une application qui reprend le travail de la
    précédente : le fichier a rempli son office, le laisser traîner donnerait
    une chaîne pleine de résidus dont on ne saurait plus lesquels font foi.
    Pour le garder — mise au point, comparaison —, employer `read`.
    """
    exchange = read(path)
    discard(path)
    return exchange


def discard(path: str) -> None:
    """Supprime un fichier d'échange consommé, sans s'émouvoir de son absence."""
    try:
        os.remove(path)
    except OSError:
        # Déjà supprimé, ou dossier en lecture seule : ce n'est pas de quoi
        # arrêter une génération qui, elle, a abouti.
        return


# ─────────────────────────────────────────────────────────────
#  Codec
# ─────────────────────────────────────────────────────────────


def encode(value: Any) -> Any:
    """Transforme une dataclass — et ce qu'elle contient — en JSON."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: encode(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, set | frozenset):
        # Trié : sans quoi le fichier changerait à chaque exécution, et `diff`
        # ne dirait plus rien.
        return sorted(encode(item) for item in value)
    if isinstance(value, list | tuple):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    return value


def decode(kind: Any, raw: Any) -> Any:
    """Reconstruit une valeur d'après l'annotation qui la décrit."""
    origin = get_origin(kind)
    if origin in (list, tuple):
        return [decode(get_args(kind)[0], item) for item in raw or []]
    if origin in (set, frozenset):
        return {decode(get_args(kind)[0], item) for item in raw or []}
    if origin is dict:
        value_kind = get_args(kind)[1]
        return {key: decode(value_kind, item) for key, item in (raw or {}).items()}
    if is_dataclass(kind) and isinstance(kind, type):
        return _build(kind, raw)
    return raw


def _build(kind: type, raw: Any) -> Any:
    """
    Reconstruit une dataclass à partir de ce que le fichier en dit.

    Les champs absents gardent leur valeur par défaut : un fichier écrit par une
    version antérieure du projet, à qui il manque un champ ajouté depuis, se
    relit sans broncher.
    """
    if not isinstance(raw, dict):
        raise ExchangeError(f"{kind.__name__} attendu, reçu {type(raw).__name__}")

    hints = get_type_hints(kind)
    known = {f.name for f in fields(kind)}
    return kind(**{key: decode(hints[key], raw[key]) for key in raw if key in known})
