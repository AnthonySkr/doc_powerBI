"""
Mode d'emploi lu dans le terminal.

L'utilisateur reçoit un dossier de quatre fichiers, dont un `README.md`. Rien
ne garantit qu'il l'ouvrira : c'est un fichier texte parmi d'autres, et le
Bloc-notes l'affiche sans mise en forme, balises comprises. Le mode d'emploi
est donc aussi lisible depuis l'application elle-même, proposé au lancement
(voir `cli.menu`) ou demandé par `--mode-emploi`.

Ce module lit le même `README.md` que celui livré à côté de l'exécutable et le
met en page pour une console : titres détachés, tableaux alignés, listes à
puces, blocs de code en retrait, le tout ramené à la largeur de l'affichage et
paginé écran par écran. Le rendu est volontairement partiel — il couvre ce
qu'emploie le mode d'emploi, pas Markdown en entier.
"""

import os
import re

from src import __version__, console, paths

__all__ = ["candidates", "show"]

README = "README.md"

# Retrait commun du corps de texte, aligné sur celui des autres messages.
INDENT = "  "


# ─────────────────────────────────────────────────────────────
#  Affichage
# ─────────────────────────────────────────────────────────────


def show() -> None:
    """Affiche le mode d'emploi, page par page."""
    source = _read()
    if source is None:
        console.blank()
        console.error(f"Mode d'emploi introuvable ({README}).")
        console.detail("Cherché dans : " + ", ".join(candidates()))
        console.blank()
        return

    _paginate(render(source))


def candidates() -> list[str]:
    """
    Emplacements consultés pour trouver le mode d'emploi, dans l'ordre.

    Exécutable : le dossier du .exe d'abord — c'est le fichier livré qui fait
    foi, comme pour la configuration et le template — puis la copie embarquée,
    qui sauve un dossier dont le `README.md` a été supprimé ou déplacé.

    En développement, c'est `tools/README.md` : le `README.md` de la racine
    s'adresse aux développeurs du projet, pas aux utilisateurs de l'outil.
    """
    if paths.is_frozen():
        folders = [paths.app_dir(), paths.bundled_dir()]
    else:
        folders = [os.path.join(paths.app_dir(), "tools")]
    return [os.path.join(folder, README) for folder in folders if folder]


def _read() -> str | None:
    """Texte du mode d'emploi, sa version inscrite ; None s'il est introuvable."""
    for candidate in candidates():
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                # `replace` et non `format` : le mode d'emploi cite la
                # configuration, où les accolades sont de mise.
                return f.read().replace("{version}", __version__)
        except OSError:
            continue
    return None


def _paginate(lines: list[str]) -> None:
    """
    Écrit les lignes en s'arrêtant à chaque écran rempli.

    Un mode d'emploi de trois cents lignes déroulé d'un trait ne laisse à
    l'écran que sa dernière page. Hors terminal — sortie redirigée — il n'y a
    personne pour appuyer sur une touche : tout est écrit d'un coup.
    """
    page = console.height()
    console.blank()

    written = 0
    for line in lines:
        console.line(line)
        written += 1
        if page and written >= page:
            written = 0
            if not _more():
                return

    console.blank()
    _wait("Entrée pour continuer")


def _more() -> bool:
    """Invite de bas de page. Faux si l'utilisateur demande à sortir."""
    return _wait("Entrée pour la suite, Q pour quitter").strip().lower() not in ("q", "quitter")


def _wait(label: str) -> str:
    """Attend une touche, sans bloquer là où il n'y a pas d'entrée."""
    if not console.is_terminal():
        return ""
    try:
        return console.ask(label)
    except Exception:  # noqa: BLE001
        # Entrée absente ou fermée : ne pas immobiliser le script.
        return "q"


# ─────────────────────────────────────────────────────────────
#  Mise en page du Markdown
# ─────────────────────────────────────────────────────────────

_RULE = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_NUMBER = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_SEPARATOR_CELL = re.compile(r"^:?-{2,}:?$")


def render(source: str) -> list[str]:
    """Met en page un texte Markdown pour la console."""
    page = _Page()
    table: list[str] = []
    fenced = False

    for raw in source.splitlines():
        stripped = raw.strip()

        if stripped.startswith("```"):
            fenced = not fenced
            page.flush()
            continue

        if fenced:
            bar = console.paint(console.glyph("v"), "frame")
            page.written(f"{INDENT}{bar} " + console.paint(raw, "key"))
            continue

        if stripped.startswith("|"):
            page.flush()
            table.append(raw)
            continue
        if table:
            page.written(*_table(table))
            table = []

        _feed(page, raw, stripped)

    if table:
        page.written(*_table(table))
    return _tidy(page.close())


def _feed(page: _Page, raw: str, stripped: str) -> None:
    """Confie une ligne de Markdown à la page en cours de composition."""
    if not stripped:
        page.written("")
        return

    if _RULE.match(raw):
        rule = console.glyph("h") * (console.WIDTH - len(INDENT) * 2)
        page.written("", console.paint(INDENT + rule, "frame"), "")
        return

    heading = _HEADING.match(stripped)
    if heading:
        page.written(*_heading(len(heading.group(1)), heading.group(2).strip()))
        return

    quote = _QUOTE.match(raw)
    if quote:
        bar = console.paint(console.glyph("v"), "warn")
        page.open("quote", f"{INDENT}{bar} ", f"{INDENT}{bar} ", quote.group(1).strip())
        return

    bullet = _BULLET.match(raw)
    if bullet:
        depth = INDENT + "  " * (len(bullet.group(1)) // 2)
        mark = console.paint(console.glyph("dot"), "frame")
        page.open("liste", f"{depth}{mark} ", depth + "  ", bullet.group(2))
        return

    number = _NUMBER.match(raw)
    if number:
        depth = INDENT + "  " * (len(number.group(1)) // 2)
        mark = console.paint(f"{number.group(2)}.", "key")
        page.open(
            "liste", f"{depth}{mark} ", depth + " " * (len(number.group(2)) + 2), number.group(3)
        )
        return

    page.more(stripped)


class _Page:
    """
    Page en cours de composition.

    Le mode d'emploi est écrit avec des lignes courtes, coupées à la main vers
    la soixante-dixième colonne. Les recouper telles quelles donnerait un texte
    en dents de scie, et découperait en deux un `**passage en gras**` à cheval
    sur deux lignes. Les lignes d'un même paragraphe sont donc recollées, puis
    remises d'un bloc à la largeur de l'affichage : c'est le paragraphe qui est
    l'unité, comme en Markdown.
    """

    def __init__(self) -> None:
        self.lines: list[str] = []
        self._kind = ""
        self._first = ""
        self._next = ""
        self._text = ""

    def open(self, kind: str, first: str, next_: str, text: str) -> None:
        """Ouvre un paragraphe d'un genre donné, avec ses retraits."""
        # Une citation s'écrit une ligne après l'autre, chacune préfixée de
        # « > » : ces lignes forment un seul paragraphe, pas une par ligne.
        if kind == "quote" and self._kind == "quote":
            self.more(text)
            return
        self.flush()
        self._kind, self._first, self._next, self._text = kind, first, next_, text

    def more(self, text: str) -> None:
        """Suite du paragraphe ouvert, ou début d'un paragraphe ordinaire."""
        if not self._kind:
            self.open("texte", INDENT, INDENT, text)
            return
        self._text = f"{self._text} {text}".strip()

    def written(self, *lines: str) -> None:
        """Ajoute des lignes déjà composées — un titre, un tableau, du code."""
        self.flush()
        self.lines.extend(lines)

    def flush(self) -> None:
        """Met en page le paragraphe ouvert, s'il y en a un."""
        if not self._kind:
            return
        self.lines.extend(line for line, _ in _compose(self._text, self._first, self._next))
        self._kind, self._text = "", ""

    def close(self) -> list[str]:
        self.flush()
        return self.lines


def _heading(level: int, text: str) -> list[str]:
    """
    Titre, d'autant plus détaché qu'il est haut.

    Niveau 1 : le titre du document, encadré comme le bandeau d'ouverture.
    Niveau 2 : une partie, sur une ligne de séparation — même dessin que les
    étapes de la génération, pour que l'ensemble ait l'air d'un seul outil.
    Au-delà : un simple intitulé en gras.
    """
    label = _plain(text)

    if level == 1:
        # Même cadre, même largeur que le bandeau d'ouverture : le mode
        # d'emploi doit avoir l'air de la même application, pas d'une annexe.
        inner = console.WIDTH - 2
        body = f" {label.upper()} "[:inner].center(inner)
        return [
            "",
            console.paint(
                console.glyph("tl") + console.glyph("h") * inner + console.glyph("tr"), "frame"
            ),
            console.paint(console.glyph("v"), "frame")
            + console.paint(body, "bold")
            + console.paint(console.glyph("v"), "frame"),
            console.paint(
                console.glyph("bl") + console.glyph("h") * inner + console.glyph("br"), "frame"
            ),
            "",
        ]

    if level == 2:
        head = f"{console.glyph('h') * 2} {console.glyph('step')} "
        fill = max(console.WIDTH - len(head) - len(label) - 3, 0)
        return [
            "",
            console.paint(head, "frame")
            + console.paint(label, "bold")
            + console.paint(" " + console.glyph("h") * fill, "frame"),
            "",
        ]

    return ["", console.paint(INDENT + label, "bold"), ""]


# ─────────────────────────────────────────────────────────────
#  Tableaux
# ─────────────────────────────────────────────────────────────


def _table(rows: list[str]) -> list[str]:
    """
    Aligne un tableau Markdown en colonnes.

    Les colonnes prennent la largeur de leur contenu, puis les plus larges sont
    rognées jusqu'à ce que l'ensemble tienne dans l'affichage : le texte qui
    dépasse passe à la ligne dans sa cellule plutôt que de déborder de l'écran.
    """
    cells = [_cells(row) for row in rows]
    cells = [row for row in cells if not _is_separator(row)]
    if not cells:
        return []

    count = max(len(row) for row in cells)
    cells = [row + [""] * (count - len(row)) for row in cells]

    gap = console.paint(f" {console.glyph('v')} ", "frame")
    widths = _widths(cells, count, available=console.WIDTH - len(INDENT) - 3 * (count - 1))

    lines = [""]
    for index, row in enumerate(cells):
        lines.extend(_row(row, widths, gap, header=index == 0))
        if index == 0:
            lines.append(
                console.paint(
                    INDENT
                    + (console.glyph("h") + console.glyph("h") + console.glyph("h")).join(
                        console.glyph("h") * width for width in widths
                    ),
                    "frame",
                )
            )
    lines.append("")
    return lines


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _is_separator(row: list[str]) -> bool:
    """La ligne `| --- | --- |` qui sépare l'en-tête du corps : rien à écrire."""
    return bool(row) and all(_SEPARATOR_CELL.match(cell) for cell in row if cell)


def _widths(cells: list[list[str]], count: int, available: int) -> list[int]:
    """Largeur de chaque colonne, rognée jusqu'à tenir dans l'affichage."""
    widths = [max(len(_plain(row[index])) for row in cells) for index in range(count)]
    while sum(widths) > available and max(widths) > 6:
        widths[widths.index(max(widths))] -= 1
    return widths


def _row(row: list[str], widths: list[int], gap: str, header: bool) -> list[str]:
    """Une ligne du tableau, sur autant de lignes que la plus haute cellule."""
    style = "bold" if header else ""
    columns = [_compose(cell, "", "", width=width, style=style) for cell, width in zip(row, widths)]
    tall = max(len(column) for column in columns)

    lines = []
    for index in range(tall):
        pieces = []
        for column, width in zip(columns, widths):
            text, visible = column[index] if index < len(column) else ("", 0)
            pieces.append(text + " " * (width - visible))
        lines.append(INDENT + gap.join(pieces).rstrip())
    return lines


# ─────────────────────────────────────────────────────────────
#  Mise à la largeur, et styles dans le fil du texte
# ─────────────────────────────────────────────────────────────

_INLINE = re.compile(
    r"\*\*(?P<bold>.+?)\*\*"
    r"|`(?P<code>[^`]+)`"
    r"|\[(?P<link>[^\]]+)\]\((?P<url>[^)]+)\)"
    r"|\*(?P<italic>[^*\n]+)\*"
)

_INLINE_STYLES = {"bold": "bold", "code": "key", "italic": "dim", "link": "bold"}


def _compose(
    text: str, first: str, next_: str, width: int = 0, style: str = ""
) -> list[tuple[str, int]]:
    """
    Découpe un texte à la largeur voulue, ses `**gras**` et `` `code` `` peints.

    Retourne des couples (ligne prête à écrire, longueur visible) : les codes
    de couleur comptent dans la longueur d'une chaîne mais pas à l'écran, et
    les colonnes d'un tableau se calent sur la seconde.
    """
    width = width or console.WIDTH
    lines: list[tuple[str, int]] = []
    prefix, room = first, width - len(_plain(first))
    current: list[str] = []
    length = 0

    for word, visible in _words(text, style):
        if current and length + 1 + visible > room:
            lines.append((prefix + " ".join(current), len(_plain(prefix)) + length))
            prefix, room = next_, width - len(_plain(next_))
            current, length = [word], visible
        else:
            length += visible + (1 if current else 0)
            current.append(word)

    if current or not lines:
        lines.append((prefix + " ".join(current), len(_plain(prefix)) + length))
    return lines


def _words(text: str, style: str = "") -> list[tuple[str, int]]:
    """
    Les mots du texte, peints, avec leur longueur visible.

    Un mot peut porter plusieurs styles — `**format projet** (`.pbip`)` en
    compte trois, sans espace entre eux : la découpe se fait sur les espaces,
    jamais sur les bornes de style, sous peine d'écrire « ( .pbip ) ».
    """
    words: list[list[tuple[str, str]]] = []
    opening = True

    for content, kind in _segments(text):
        for piece in re.split(r"(\s+)", content):
            if not piece:
                continue
            if piece.isspace():
                opening = True
                continue
            if opening or not words:
                words.append([])
                opening = False
            words[-1].append((piece, kind or style))

    return [
        (
            "".join(console.paint(piece, kind) if kind else piece for piece, kind in word),
            sum(len(piece) for piece, _ in word),
        )
        for word in words
    ]


def _segments(text: str, style: str = "") -> list[tuple[str, str]]:
    """
    Découpe une ligne en fragments (texte, style), balises ôtées.

    Les styles s'imbriquent — le mode d'emploi écrit `` **au format (`.pbip`)**
    `` — et la console, elle, ne les imbrique pas : une couleur se referme d'un
    coup. C'est donc le style le plus intérieur qui l'emporte, le seul choix
    qui ne laisse jamais une balise s'écrire en clair.
    """
    pieces: list[tuple[str, str]] = []
    position = 0

    for match in _INLINE.finditer(text):
        if match.start() > position:
            pieces.append((text[position : match.start()], style))
        for name, kind in _INLINE_STYLES.items():
            caught = match.group(name)
            if caught is None:
                continue
            # Le contenu d'un `code` est littéral : on n'y cherche pas de balise.
            pieces.extend([(caught, kind)] if name == "code" else _segments(caught, kind))
            if name == "link":
                pieces.append((f" ({match.group('url')})", "dim"))
            break
        position = match.end()

    if position < len(text):
        pieces.append((text[position:], style))
    return pieces


def _plain(text: str) -> str:
    """Le texte tel qu'il s'affiche : sans balise Markdown ni code de couleur."""
    without_color = re.sub(r"\033\[[0-9;]*m", "", text)
    return "".join(content for content, _ in _segments(without_color))


def _tidy(lines: list[str]) -> list[str]:
    """Supprime les lignes vides en double, et celles des extrémités."""
    tidied: list[str] = []
    for line in lines:
        if not line.strip() and (not tidied or not tidied[-1].strip()):
            continue
        tidied.append(line)
    while tidied and not tidied[-1].strip():
        tidied.pop()
    return tidied
