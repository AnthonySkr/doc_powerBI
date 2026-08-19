"""
Le petit langage d'expressions du fichier de configuration.

Trois usages, tous alimentés par le même « contexte » (report, model, inputs,
styles, plus l'item courant d'une boucle) :

    render("{{ report.name }}", ctx)      texte avec variables substituées
    resolve_items("model.tables", ctx)    collection parcourue par `over:`
    evaluate("!inputs.detail", ctx)       condition `when:`
"""

import re
from typing import Any

_VAR_PATTERN = re.compile(r"\{\{\s*(.+?)\s*\}\}")


# ─────────────────────────────────────────────────────────────
#  Substitution des variables {{ ... }}
# ─────────────────────────────────────────────────────────────


def render(value: Any, context: dict[str, Any]) -> str:
    """Remplace les `{{ expression }}` d'une chaîne par leur valeur."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)

    return _VAR_PATTERN.sub(lambda m: to_text(resolve(m.group(1), context)), value).strip()


def render_list(value: Any, context: dict[str, Any]) -> list[str]:
    """Comme `render`, mais destiné aux expressions qui produisent une liste."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [text for text in map(to_text, value) if text]

    if isinstance(value, str):
        match = _VAR_PATTERN.fullmatch(value.strip())
        if match:
            resolved = resolve(match.group(1), context)
            if isinstance(resolved, (list, tuple, set)):
                return [text for text in map(to_text, resolved) if text]
            return [to_text(resolved)] if to_text(resolved) else []
        text = render(value, context)
        return [text] if text else []

    return [to_text(value)]


def resolve_items(expression: Any, context: dict[str, Any]) -> list[Any]:
    """
    Résout l'expression `over:` d'une boucle ou d'un tableau.

    Contrairement à `render_list`, les objets sont retournés tels quels : la
    boucle a besoin des mesures ou des pages, pas de leur représentation texte.
    """
    if not expression:
        return []
    if isinstance(expression, (list, tuple)):
        return list(expression)

    value = resolve(str(expression).strip().strip("{} "), context)

    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return list(value.values())
    return [value]


def resolve(expression: str, context: dict[str, Any]) -> Any:
    """
    Résout une expression.

    Formes admises :
      report.name              chemin pointé (attribut ou clé de dictionnaire)
      a + b                    concaténation (listes ou chaînes)
    """
    expression = expression.strip()

    if "+" not in expression:
        return _lookup(expression, context)

    parts = [resolve(part, context) for part in expression.split("+")]
    if not any(isinstance(part, (list, tuple, set)) for part in parts):
        return "".join(to_text(part) for part in parts)

    merged: list[Any] = []
    for part in parts:
        if isinstance(part, set):
            merged.extend(sorted(part))
        elif isinstance(part, (list, tuple)):
            merged.extend(part)
        elif part not in (None, ""):
            merged.append(part)
    return merged


def _lookup(path: str, context: dict[str, Any]) -> Any:
    current: Any = context
    for part in path.split("."):
        part = part.strip()
        if not part:
            return None
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            if not hasattr(current, part):
                return None
            current = getattr(current, part)
    return current


def to_text(value: Any) -> str:
    """Représentation texte d'une valeur du contexte."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, set):
        return ", ".join(sorted(str(item) for item in value))
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


# ─────────────────────────────────────────────────────────────
#  Conditions `when`
# ─────────────────────────────────────────────────────────────


def evaluate(condition: Any, context: dict[str, Any]) -> bool:
    """
    Évalue une condition `when`.

    Formes admises :
      inputs.pages_secondaires        vrai si la valeur est vraie
      !inputs.pages_secondaires       négation
      ref.kind == mesure              égalité (textuelle, insensible à la casse)
    """
    if condition is None:
        return True
    if isinstance(condition, bool):
        return condition

    expression = str(condition).strip()
    if not expression:
        return True

    if expression.startswith("!"):
        return not evaluate(expression[1:], context)

    for operator in ("!=", "=="):
        if operator in expression:
            left_expr, right_expr = expression.split(operator, 1)
            left = to_text(resolve(left_expr, context)).strip().lower()
            right = right_expr.strip().strip("'\"").lower()
            return (left == right) if operator == "==" else (left != right)

    return _is_truthy(resolve(expression, context))


def _is_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "non", "no", "0")
    return bool(value)
