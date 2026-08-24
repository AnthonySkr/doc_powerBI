"""
Valeurs par défaut de la configuration.

Toute clé absente de `config_doc_pbi.yaml` est complétée depuis ce dictionnaire :
le fichier de l'utilisateur n'a donc besoin de contenir que ce qu'il change.
Les commentaires du YAML restent la documentation de référence.
"""

from typing import Any

DEFAULT_CONFIG_PATH = "config_doc_pbi.yaml"

DEFAULTS: dict[str, Any] = {
    "document": {
        # Conserver les réponses aux questions à côté du document, et les
        # reproposer à la génération suivante.
        "remember_answers": True,
        "answers_file": "reponses_{{ report.name }}.yaml",
        "template": "template-doc-pbib.docx",
        "output_dir": "output",
        "output_name": "documentation_{{ report.name }}.docx",
        "cover": {"placeholder": "", "text": "", "bold": True},
        "header_footer": {"replacements": []},
        "properties": {},
    },
    "styles": {
        "heading_1": "Heading 1",
        "heading_2": "Heading 2",
        "heading_3": "Heading 3",
        "heading_4": "Heading 4",
        "subtitle": "Sous-titre 3",
        "normal": "Normal",
        "bullet": "List Bullet",
        "code": "Code DAX",
        "image": "Image Placeholder",
        "caption": "Legende",
        "todo": "A completer",
        "table": "Tableau Reference",
        "table_data": "Tableau Donnees",
        "ref_header": "Ref Entete",
        "ref_number": "Ref Numero",
        "ref_role": "Ref Role",
        "ref_value": "Ref Valeur",
        "technical_id": "Id technique",
        "fallback": "Normal",
    },
    "rendering": {
        "page_break_before_heading_1": True,
        "image_placeholder": {
            "text_format": "[IMAGE] {description}",
            "caption_format": "Figure {n} — {description}",
            "show_caption": False,
            "numbering": True,
            "empty_paragraph_after": True,
        },
        "user_fill": {
            "placeholder_text": "[À compléter]",
            "show_placeholder": True,
            "style": "{{ styles.todo }}",
        },
        "table_of_contents": {
            "update": True,
            "update_all_fields": False,
            "update_with_word": False,
            "levels": "",
        },
        "links": {
            "enabled": True,
            "style": "Hyperlink",
            "bookmark_prefix": "",
            "auto": {
                "enabled": True,
                "source": "model.tables_with_measures",
                "target": "measure:{{ measure.name }}",
                "in_code": True,
                "skip_self": True,
                "first_occurrence_only": False,
                "case_sensitive": False,
                "min_length": 2,
                "exclude": [],
            },
        },
        "property": {
            "label_style": "{{ styles.subtitle }}",
            "value_style": "{{ styles.normal }}",
            "fallback_style": "{{ styles.todo }}",
            "empty_paragraph_after": False,
        },
    },
    "data": {
        "pages": {"exclude_hidden": True, "exclude_names": [], "sort_by": "report_order"},
        "visuals": {
            "exclude_types": [],
            "exclude_titles": [],
            "only_with_measures": False,
            "sort_by": "title",
            "groups": {
                "enabled": True,
                "keep_empty": False,
                "exclude_titles": [],
                "sort_by": "position",
                "member_sort_by": "position",
            },
        },
        "tables": {
            "exclude_hidden": True,
            "exclude_names": [],
            "sort_by": "name",
            "ignore_sources": [],
            "steps": {
                "exclude_unnamed": True,
                "exclude_names": [],
                "exclude_prefixes": [],
            },
        },
        "measures": {
            "scope": "used_in_report",
            "include_hidden": False,
            "include_referenced": True,
            "group_by": "table",
            "sort_by": "name",
        },
    },
    "merge": {
        "enabled": True,
        "keep_user_text": True,
        "backup": True,
        "backup_dir": ".versions",
        "highlight_changed": "yellow",
        "highlight_new": "none",
        # Annexe recueillant, en fin de document, ce qui n'a pas pu être
        # replacé : élément disparu du rapport, bloc retiré du plan, donnée du
        # script retouchée à la main. Rien n'est jeté en silence.
        "orphans": {
            "enabled": True,
            "title": "Contenu non replacé",
            "intro": "",
        },
    },
    "inputs": [],
    "sections": [],
}
