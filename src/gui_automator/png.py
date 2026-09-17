"""
Écrire un PNG, sans bibliothèque d'images.

Le projet ne dépend d'aucune bibliothèque de traitement d'image, et n'a pas à
en dépendre pour ce qu'il en fait : un aplat de couleur (`fake`) et quelques
rectangles tracés sur une capture (`canvas.outline`, pour le calibrage). Un
PNG, c'est un en-tête, des lignes compressées et une fin de fichier — une
trentaine de lignes qui évitent une dépendance de plus à installer sur le
poste de l'utilisateur.

Les pixels circulent partout ici sous la même forme : trois octets par pixel,
R, G puis B, lignes du haut vers le bas, sans remplissage en fin de ligne.
C'est ce que `mss` retourne dans `ScreenShot.rgb`.
"""

import struct
import zlib

__all__ = ["encode", "solid"]


def encode(width: int, height: int, rgb: bytes) -> bytes:
    """
    Image PNG à partir de ses pixels bruts.

    `rgb` fait exactement `width * height * 3` octets ; plus court, l'image est
    complétée de noir plutôt que refusée — une capture tronquée vaut mieux
    qu'une séance interrompue.
    """
    width, height = max(width, 1), max(height, 1)
    expected = width * height * 3
    pixels = rgb[:expected].ljust(expected, b"\x00")

    # Chaque ligne est précédée de son octet de filtre — aucun filtre ici.
    stride = width * 3
    raw = b"".join(b"\x00" + pixels[y * stride : (y + 1) * stride] for y in range(height))

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(raw, 6)),
            _chunk(b"IEND", b""),
        ]
    )


def solid(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """Image PNG d'une seule couleur."""
    width, height = max(width, 1), max(height, 1)
    return encode(width, height, bytes(color) * (width * height))


def _chunk(kind: bytes, payload: bytes) -> bytes:
    """Un bloc PNG : longueur, type, contenu, et le CRC des deux derniers."""
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))
