"""
Découpage d'un script Power Query (`let ... in ...`) en étapes nommées.

Le code M est du texte : le découpage se fait donc à la main, en ignorant les
séparateurs situés à l'intérieur d'une chaîne ou d'une parenthèse.
"""

import re

from src.models.data_models import TransformationStep


def parse_steps(m_code: str) -> list[TransformationStep]:
    """
    Découpe un script `let ... in ...` en étapes.

    Chaque étape retient son expression deux fois : ramenée sur une ligne, pour
    tenir dans une cellule de tableau, et telle qu'écrite, pour être reproduite
    avec son indentation dans un bloc de code.
    """
    body = _let_body(m_code) if m_code else None
    if body is None:
        return []

    steps: list[TransformationStep] = []
    for chunk in split_top_level(body, ","):
        parts = split_top_level(chunk, "=")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        if not name:
            continue
        raw = dedent("=".join(parts[1:]))
        steps.append(
            TransformationStep(
                name=_clean_identifier(name),
                expression=" ".join(raw.split()),
                raw_expression=raw,
            )
        )
    return steps


def source_expression(steps: list[TransformationStep], m_code: str) -> str:
    """
    Paramètres de connexion de la table : l'expression de son étape source,
    telle qu'écrite — son indentation fait partie de ce qui est documenté.
    """
    for step in steps:
        if step.name.lower() in ("source", "src"):
            return step.raw_expression
    if steps:
        return steps[0].raw_expression
    return dedent(m_code)[:500]


def split_top_level(text: str, separator: str) -> list[str]:
    """Découpe une chaîne sur un séparateur situé hors chaîne et hors parenthèses."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False

    for char in text:
        if char == '"':
            in_string = not in_string
        elif not in_string:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == separator and depth == 0:
                parts.append("".join(current))
                current = []
                continue
        current.append(char)

    parts.append("".join(current))
    return parts


def dedent(text: str) -> str:
    """
    Ramène un bloc de code à la marge en gardant son indentation relative.

    Le code M d'une partition est indenté par rapport au fichier .tmdl qui le
    contient : sans cela, chaque ligne du document hériterait de cette marge.
    """
    lines = text.strip("\n").split("\n")
    indented = [line for line in lines[1:] if line.strip()]
    margin = min((len(line) - len(line.lstrip()) for line in indented), default=0)
    return "\n".join([lines[0].strip()] + [line[margin:].rstrip() for line in lines[1:]]).rstrip()


def _let_body(m_code: str) -> str | None:
    """Isole le corps entre `let` et le `in` final (hors chaînes et parenthèses)."""
    match = re.search(r"\blet\b", m_code)
    if not match:
        return None

    body = m_code[match.end() :]
    last_in = None
    for token in re.finditer(r"\bin\b", body):
        if _depth_at(body, token.start()) == 0:
            last_in = token.start()

    return body[:last_in] if last_in is not None else body


def _depth_at(text: str, index: int) -> int:
    """Profondeur de parenthésage à une position, en ignorant les chaînes."""
    depth = 0
    in_string = False
    for char in text[:index]:
        if char == '"':
            in_string = not in_string
        elif not in_string:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
    return depth


def _clean_identifier(name: str) -> str:
    """Nettoie un identifiant Power Query : `#"Lignes filtrées"` → `Lignes filtrées`."""
    name = name.strip()
    if name.startswith('#"') and name.endswith('"'):
        return name[2:-1]
    return name.strip('"')
