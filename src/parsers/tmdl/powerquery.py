"""
Découpage d'un script Power Query (`let ... in ...`) en étapes nommées.

Le code M est du texte : le découpage se fait donc à la main, en ignorant les
séparateurs situés à l'intérieur d'une chaîne ou d'une parenthèse.
"""

import re


def parse_steps(m_code: str) -> list[dict[str, str]]:
    """
    Découpe un script `let ... in ...` en étapes.

    Returns:
        Liste de {"name": nom de l'étape, "expression": expression associée}
    """
    body = _let_body(m_code) if m_code else None
    if body is None:
        return []

    steps: list[dict[str, str]] = []
    for chunk in split_top_level(body, ","):
        parts = split_top_level(chunk.strip(), "=")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        if not name:
            continue
        expression = "=".join(parts[1:]).strip()
        steps.append({"name": _clean_identifier(name), "expression": " ".join(expression.split())})
    return steps


def source_expression(steps: list[dict[str, str]], m_code: str) -> str:
    """Détermine la source de la table (paramètres de connexion)."""
    for step in steps:
        if step["name"].lower() in ("source", "src"):
            return step["expression"]
    if steps:
        return steps[0]["expression"]
    return " ".join(m_code.split())[:500]


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
