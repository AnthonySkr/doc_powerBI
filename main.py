"""Point d'entrée principal — Génération de documentation Power BI depuis un .pbip."""

import os
import sys

from parsers.tmdl_parser import load_all_measures_from_model
from parsers.report_parser import parse_report
from parsers.dependency_analyzer import (
    analyze_all_dependencies,
    get_measures_used_in_report,
)
from generators.word_generator import generate_word_documentation

template_file = "template-doc-pbib.docx"

EXCLUDED_TYPES = {"actionButton", "pageNavigator", "image", "shape"}


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


def main() -> None:
    if len(sys.argv) > 1:
        pbip_path = sys.argv[1].strip().strip('"')
    else:
        pbip_path = input("Chemin vers le fichier .pbip : ").strip().strip('"')

    if not os.path.isfile(pbip_path):
        print(f"Fichier introuvable : '{pbip_path}'")
        sys.exit(1)

    pbip_name = os.path.splitext(os.path.basename(pbip_path))[0]
    output_dir = os.path.join(os.path.dirname(os.path.abspath(pbip_path)), "output")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 65)
    print(f"  Rapport : {pbip_name}")
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

    # ── Mesures DAX ──
    print("─" * 65)
    print("  Étape 1 — Chargement des mesures DAX")
    print("─" * 65)
    all_measures = load_all_measures_from_model(semantic_dir)
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
    print()

    # ── Mesures utilisées ──
    measures_used = get_measures_used_in_report(report, all_measures)
    report.measures_used_in_report = measures_used

    directly_used: set[str] = set()
    for p in report.pages:
        for v in p.visuals:
            for e in v.elements:
                if e.type_category == "Mesure":
                    directly_used.add(e.query_ref.split(".")[-1])

    print(f"  Mesures dans les visuels     : {len(directly_used)}")
    print(f"  Mesures totales (+ deps)     : {len(measures_used)}")
    print()

    # ── Génération Word ──
    print("─" * 65)
    print("  Étape 4 — Génération du document")
    print("─" * 65)
    word_path = os.path.join(output_dir, f"documentation_{pbip_name}.docx")
    result = generate_word_documentation(
        report,
        all_measures,
        word_path,
        template_path=template_file,
        excluded_visual_types=EXCLUDED_TYPES,
    )
    print(f"  {result}")
    print()
    print("=" * 65)
    print(f"  Terminé — Sortie dans : {output_dir}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
