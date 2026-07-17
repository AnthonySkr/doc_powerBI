"""Génération du document Word de documentation."""

from docx import Document
from models.data_models import PowerBIReport, DaxMeasure


def generate_word_documentation(
    report: PowerBIReport,
    all_measures: dict[str, DaxMeasure],
    output_path: str = "documentation_powerbi.docx",
) -> str:
    """Génère la documentation Word complète du rapport."""
    doc = Document()
    doc.add_heading(f"Documentation — {report.name}", 0)

    for page_idx, page in enumerate(report.pages, 1):
        doc.add_heading(f"{page_idx} — {page.display_name}", level=2)

        # Filtres de page
        if page.filters:
            filters_str = " ; ".join(sorted(set(f.to_string() for f in page.filters)))
            doc.add_paragraph(f"Filtres de page : {filters_str}")
        else:
            doc.add_paragraph("Aucun filtre explicite sur cette page.")
        doc.add_paragraph("")

        # Visuels avec mesures
        visual_counter = 0
        for visual in page.visuals:
            if not visual.has_measures:
                continue

            visual_counter += 1
            doc.add_heading(f"{page_idx}.{visual_counter} {visual.title}", level=3)
            doc.add_paragraph(f"Type : {visual.visual_type}")

            # Classer les éléments par rôle
            measures_values = [
                e.display_name
                for e in visual.elements
                if e.type_category == "Mesure" and e.role.lower() in ("values", "y", "size")
            ]
            measures_y2 = [
                e.display_name
                for e in visual.elements
                if e.type_category == "Mesure" and e.role.lower() == "y2"
            ]
            axes = [
                e.display_name
                for e in visual.elements
                if e.type_category != "Mesure"
                and e.role.lower() in ("category", "rows", "columns", "x")
            ]

            # Éléments pas encore classés
            classified_names = set(measures_values + measures_y2 + axes)
            others = [
                e.display_name for e in visual.elements if e.display_name not in classified_names
            ]

            has_axes = bool(axes) and bool(measures_values or measures_y2)

            if has_axes:
                if measures_values:
                    doc.add_paragraph(
                        f"Mesures (Axe Y / Valeurs) : {', '.join(sorted(measures_values))}"
                    )
                if measures_y2:
                    doc.add_paragraph(
                        f"Mesures (Axe Y2 / Secondaire) : {', '.join(sorted(measures_y2))}"
                    )
                if axes:
                    doc.add_paragraph(f"Axes / Catégories : {', '.join(sorted(axes))}")
                if others:
                    doc.add_paragraph(f"Autres éléments : {', '.join(sorted(others))}")
            else:
                all_display = []
                for e in sorted(
                    visual.elements,
                    key=lambda x: (x.type_category != "Mesure", x.display_name),
                ):
                    all_display.append(f"{e.display_name} ({e.type_category}, rôle: {e.role})")
                if all_display:
                    doc.add_paragraph(f"Éléments : {' ; '.join(all_display)}")

            # Filtres du visuel
            if visual.filters:
                filters_str = " ; ".join(sorted(set(f.to_string() for f in visual.filters)))
                doc.add_paragraph(f"Filtres du visuel : {filters_str}")
            else:
                doc.add_paragraph("Aucun filtre spécifique.")

            doc.add_paragraph("")

    # ── Récapitulatif des mesures ──
    measures_in_report: set[str] = set()
    for page in report.pages:
        for visual in page.visuals:
            for e in visual.elements:
                if e.type_category == "Mesure":
                    parts = e.query_ref.split(".")
                    measures_in_report.add(parts[-1] if parts else e.display_name)

    if measures_in_report:
        doc.add_page_break()
        doc.add_heading("Récapitulatif des mesures DAX utilisées", level=1)

        # Organiser par table → dossier
        organized: dict[str, dict[str, list[str]]] = {}
        for name in sorted(measures_in_report):
            if name in all_measures:
                m = all_measures[name]
                organized.setdefault(m.table_name, {}).setdefault(m.display_folder, []).append(name)
            else:
                organized.setdefault("Inconnue", {}).setdefault("Racine", []).append(name)

        for table in sorted(organized.keys()):
            doc.add_heading(f"Table : {table}", level=2)
            for folder in sorted(organized[table].keys()):
                if folder != "Racine":
                    doc.add_heading(f"Dossier : {folder}", level=3)
                for measure_name in sorted(organized[table][folder]):
                    doc.add_paragraph(f"• {measure_name}", style="List Bullet")
                    if measure_name in all_measures:
                        m = all_measures[measure_name]
                        if m.expression:
                            expr_preview = m.expression[:300]
                            if len(m.expression) > 300:
                                expr_preview += "..."
                            doc.add_paragraph(f"  {expr_preview}")
                        if m.description:
                            doc.add_paragraph(f"  Description : {m.description}")

    doc.save(output_path)
    return f"Documentation Word : '{output_path}'"
