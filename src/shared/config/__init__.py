"""
Configuration du document : chargement du YAML et langage d'expressions.

    from src.shared.config import load_config, render, evaluate
"""

from src.shared.config.defaults import DEFAULT_CONFIG_PATH, DEFAULT_OUTPUT_DIR
from src.shared.config.doc_config import DocConfig, load_config
from src.shared.config.expressions import (
    evaluate,
    printable,
    render,
    render_list,
    resolve,
    resolve_items,
    resolve_options,
    to_text,
)

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_OUTPUT_DIR",
    "DocConfig",
    "evaluate",
    "load_config",
    "printable",
    "render",
    "render_list",
    "resolve",
    "resolve_items",
    "resolve_options",
    "to_text",
]
