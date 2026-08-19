"""
Configuration du document : chargement du YAML et langage d'expressions.

    from src.config import load_config, render, evaluate
"""

from src.config.defaults import DEFAULT_CONFIG_PATH
from src.config.doc_config import DocConfig, load_config
from src.config.expressions import (
    evaluate,
    render,
    render_list,
    resolve,
    resolve_items,
    to_text,
)

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DocConfig",
    "evaluate",
    "load_config",
    "render",
    "render_list",
    "resolve",
    "resolve_items",
    "to_text",
]
