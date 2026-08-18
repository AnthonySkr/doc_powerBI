"""Point d'entrée principal — Génération de documentation Power BI depuis un .pbip.

La structure du document est décrite dans config_doc_pbi.yaml : ce script se
contente de collecter les données du .pbip, de poser les questions déclarées
dans la configuration, puis de lancer la génération.
"""

import argparse
import os
import sys
from typing import Any

from src.doc_config import DEFAULT_CONFIG_PATH, DocConfig, load_config, render
from src.generators.data_context import build_context
from src.generators.word_generator import generate_word_documentation
from src.parsers.dependency_analyzer import (
    analyze_all_dependencies,
    get_measures_used_in_report,
)
from src.parsers.report_parser import parse_report
from src.parsers.tmdl_parser import (
    load_all_measures_from_model,
    load_all_tables_from_model,
)


def find_pbip_components(pbip_path: str) -> tuple[str | None, str | None]:
    """Identifie les dossiers SemanticModel et Report depuis un .pbip."""
    base_dir = os.path.dirname(os.path.abspath(pbip_path))
    name = os.path.splitext(os.path.basename(pbip_path))[0]

    semantic = None
    for suffix in (".SemanticModel", ".Dataset"):
        candidate = os.path.join(base_dir, f"{name}{suffix}")
        if os.path.isdir(candidate):
            semantic = candidate
            break

    report = None
    candidate = os.path.join(base_dir, f"{name}.Report")
    if os.path.isdir(candidate):
        report = candidate

    return semantic, report


# ─────────────────────────────────────────────────────────────
#  Saisies utilisateur (section `inputs` de la configuration)
# ─────────────────────────────────────────────────────────────


def ask_inputs(config: DocConfig, base_context: dict[str, Any]) -> dict[str, Any]:
    """Pose les questions déclarées dans la configuration."""
    answers: dict[str, Any] = {}
    if not config.inputs:
        return answers

    print("─" * 65)
    print("  Renseignements")
    print("─" * 65)

    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue

        context = {**base_context, "inputs": answers}
        label = render(item.get("label") or key, context)
        kind = item.get("type", "text")

        if kind == "confirm":
            answers[key] = _ask_confirm(label, bool(item.get("default", False)))
        elif kind == "choice":
            answers[key] = _ask_choice(label, item.get("options") or [], item.get("default"))
        else:
            default = render(item.get("default"), context)
            answers[key] = _ask_text(label, default, multiline=(kind == "textarea"))

    print()
    return answers


def default_inputs(config: DocConfig, base_context: dict[str, Any]) -> dict[str, Any]:
    """Valeurs par défaut des `inputs`, utilisées en mode non interactif."""
    answers: dict[str, Any] = {}
    for item in config.inputs:
        key = item.get("id")
        if not key:
            continue
        value = item.get("default")
        context = {**base_context, "inputs": answers}
        answers[key] = render(value, context) if isinstance(value, str) else value
    return answers


def _ask_confirm(label: str, default: bool) -> bool:
    hint = "[O/n]" if default else "[o/N]"
    answer = input(f"  {label} {hint} ").strip().lower()
    if not answer:
        return default
    return answer in ("o", "oui", "y", "yes", "1")


def _ask_text(label: str, default: str, multiline: bool = False) -> str:
    if multiline:
        print(f"  {label} (ligne vide pour terminer)")
        return _read_lines("  > ") or default

    suffix = f" [{default}]" if default else ""
    answer = input(f"  {label}{suffix} : ").strip()
    return answer or default


def _ask_choice(label: str, options: list[Any], default: Any) -> Any:
    print(f"  {label}")
    for index, option in enumerate(options, start=1):
        print(f"    {index}. {option}")
    answer = input(f"  Choix [1-{len(options)}] : ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        return options[int(answer) - 1]
    return default if default is not None else (options[0] if options else "")


def _read_lines(prompt: str) -> str:
    lines: list[str] = []
    while True:
        line = input(prompt)
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


def make_text_provider(enabled: bool):
    """
    Retourne le callback proposant à l'utilisateur de modifier les textes
    types des blocs `editable`. Si désactivé, le texte du YAML est conservé.
    """
    if not enabled:
        return None

    def provider(block: dict[str, Any], default_text: str) -> str:
        label = block.get("prompt") or block.get("id") or "texte"
        print()
        print(f"  ── {label}")
        print(f"     « {default_text} »")
        if not _ask_confirm("     Modifier ce texte ?", False):
            return default_text
        print("     Nouveau texte (ligne vide pour terminer) :")
        return _read_lines("     > ") or default_text

    return provider


# ─────────────────────────────────────────────────────────────
#  Programme principal
# ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Génère la documentation Word d'un rapport Power BI (.pbip)."
    )
    parser.add_argument("pbip", nargs="?", help="Chemin vers le fichier .pbip")
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Fichier de configuration YAML (défaut : {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "-y",
        "--no-input",
        action="store_true",
        help="Ne pose aucune question : utilise les valeurs par défaut du YAML",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    pbip_path = (args.pbip or input("Chemin vers le fichier .pbip : ")).strip().strip('"')
    if not os.path.isfile(pbip_path):
        print(f"Fichier introuvable : '{pbip_path}'")
        sys.exit(1)

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Configuration : {e}")
        sys.exit(1)

    pbip_name = os.path.splitext(os.path.basename(pbip_path))[0]
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(pbip_path)),
        config.document.get("output_dir", "output"),
    )
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 65)
    print(f"  Rapport : {pbip_name}")
    print(f"  Config  : {config.path}")
    print("=" * 65)

    semantic_dir, report_dir = find_pbip_components(pbip_path)

    if not semantic_dir:
        print(f"Dossier SemanticModel introuvable pour '{pbip_name}'")
        sys.exit(1)
    if not report_dir:
        print(f"Dossier Report introuvable pour '{pbip_name}'")
        sys.exit(1)

    print(f"  SemanticModel : {os.path.basename(semantic_dir)}")
    print(f"  Report        : {os.path.basename(report_dir)}")
    print()

    # ── Modèle sémantique ──
    print("─" * 65)
    print("  Étape 1 — Chargement du modèle sémantique")
    print("─" * 65)
    all_measures = load_all_measures_from_model(semantic_dir)
    model_tables = load_all_tables_from_model(semantic_dir)
    print()

    # ── Dépendances ──
    if all_measures:
        print("─" * 65)
        print("  Étape 2 — Analyse des dépendances")
        print("─" * 65)
        analyze_all_dependencies(all_measures)
        print(f"  Dépendances calculées pour {len(all_measures)} mesures")
        print()

    # ── Rapport ──
    print("─" * 65)
    print("  Étape 3 — Lecture du rapport")
    print("─" * 65)
    report = parse_report(report_dir, report_name=pbip_name)
    report.all_measures = all_measures
    report.tables = model_tables
    report.measures_used_in_report = get_measures_used_in_report(report, all_measures)
    print()

    directly_used = {
        element.query_ref.split(".")[-1]
        for page in report.pages
        for visual in page.visuals
        for element in visual.elements
        if element.type_category == "Mesure"
    }
    print(f"  Mesures dans les visuels     : {len(directly_used)}")
    print(f"  Mesures totales (+ deps)     : {len(report.measures_used_in_report)}")
    print()

    # ── Saisies utilisateur ──
    base_context = {"report": report, "inputs": {}, "styles": config.styles}
    inputs = (
        default_inputs(config, base_context) if args.no_input else ask_inputs(config, base_context)
    )

    # ── Génération Word ──
    print("─" * 65)
    print("  Étape 4 — Génération du document")
    print("─" * 65)

    context = build_context(report, all_measures, config, inputs)
    output_name = render(config.document.get("output_name"), context) or (
        f"documentation_{pbip_name}.docx"
    )
    word_path = os.path.join(output_dir, output_name)

    text_provider = make_text_provider(
        not args.no_input and bool(inputs.get("editer_textes", False))
    )

    result = generate_word_documentation(config, context, word_path, text_provider)
    print(f"  {result}")
    print()
    print("=" * 65)
    print(f"  Terminé — Sortie dans : {output_dir}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
