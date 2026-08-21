"""Tests de la lecture des fichiers .tmdl : mesures, propriétés, Power Query."""

import unittest

from src.parsers.tmdl.columns import extract_calculated_columns
from src.parsers.tmdl.measures import extract_measures
from src.parsers.tmdl.powerquery import parse_steps, source_expression
from src.parsers.tmdl.reader import table_name
from src.parsers.tmdl.tables import parse_table

VENTES = """table Ventes

\tmeasure 'Chiffre d''affaires' = SUM(Ventes[Montant])
\t\tformatString: #,0
\t\tdisplayFolder: Indicateurs

\tmeasure Marge = ```
\t\t\tDIVIDE([Resultat], [Chiffre d'affaires])
\t\t\t```
\t\tdescription: Taux de marge
\t\tlineageTag: abc-123

\tmeasure 'Marge %' =
\t\tDIVIDE(
\t\t\t[Marge],
\t\t\t100
\t\t)
\t\tisHidden

\tcolumn Montant
\t\tdataType: double

\tpartition Ventes = m
\t\tsource =
\t\t\tlet
\t\t\t    Source = Sql.Database("srv", "db"),
\t\t\t    #"Lignes filtrees" = Table.SelectRows(Source, each [Actif] = true)
\t\t\tin
\t\t\t    #"Lignes filtrees"
"""


class MeasureExtractionTest(unittest.TestCase):
    def setUp(self):
        self.measures = {m.name: m for m in extract_measures(VENTES, "Ventes")}

    def test_toutes_les_mesures_sont_trouvees(self):
        self.assertEqual(sorted(self.measures), ["Chiffre d'affaires", "Marge", "Marge %"])

    def test_apostrophe_doublee_dans_le_nom(self):
        self.assertIn("Chiffre d'affaires", self.measures)

    def test_expression_inline(self):
        self.assertEqual(self.measures["Chiffre d'affaires"].expression, "SUM(Ventes[Montant])")

    def test_expression_entre_backticks(self):
        self.assertEqual(
            self.measures["Marge"].expression, "DIVIDE([Resultat], [Chiffre d'affaires])"
        )

    def test_expression_multi_lignes_sans_backticks(self):
        self.assertEqual(self.measures["Marge %"].expression, "DIVIDE(\n\t[Marge],\n\t100\n)")

    def test_proprietes_reprises(self):
        measure = self.measures["Chiffre d'affaires"]
        self.assertEqual(measure.format_string, "#,0")
        self.assertEqual(measure.display_folder, "Indicateurs")
        self.assertEqual(measure.table_name, "Ventes")

    def test_description_et_lineage_tag_ignore(self):
        self.assertEqual(self.measures["Marge"].description, "Taux de marge")

    def test_dossier_par_defaut(self):
        self.assertEqual(self.measures["Marge"].display_folder, "Racine")

    def test_mesure_masquee(self):
        self.assertTrue(self.measures["Marge %"].is_hidden)
        self.assertFalse(self.measures["Marge"].is_hidden)

    def test_bloc_column_ignore(self):
        self.assertNotIn("Montant", self.measures)

    def test_fichier_sans_mesure(self):
        self.assertEqual(extract_measures("table Vide\n\tcolumn A\n", "Vide"), [])


class TableTest(unittest.TestCase):
    def test_nom_de_table_quote(self):
        self.assertEqual(table_name("table 'Ventes N-1'\n"), "Ventes N-1")

    def test_nom_de_table_simple(self):
        self.assertEqual(table_name(VENTES), "Ventes")

    def test_table_visible(self):
        self.assertFalse(parse_table(VENTES).is_hidden)

    def test_table_masquee(self):
        self.assertTrue(parse_table("table Calendrier\n\tisHidden\n\n\tcolumn A\n").is_hidden)

    def test_is_hidden_d_un_sous_bloc_ignore(self):
        content = "table Ventes\n\n\tcolumn Montant\n\t\tisHidden\n"
        self.assertFalse(parse_table(content).is_hidden)

    def test_source_et_etapes(self):
        table = parse_table(VENTES)
        self.assertEqual(
            [step.name for step in table.transformation_steps],
            ["Source", "Lignes filtrees"],
        )
        self.assertEqual(table.source, 'Sql.Database("srv", "db")')


class PowerQueryTest(unittest.TestCase):
    def test_virgule_dans_une_chaine_non_separatrice(self):
        steps = parse_steps('let A = Text.From("x, y"), B = 1 in B')
        self.assertEqual([step.name for step in steps], ["A", "B"])

    def test_virgule_entre_parentheses_non_separatrice(self):
        steps = parse_steps("let A = F(1, 2, 3) in A")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].expression, "F(1, 2, 3)")

    def test_identifiant_echappe(self):
        self.assertEqual(parse_steps('let #"Lignes filtrées" = 1 in x')[0].name, "Lignes filtrées")

    def test_source_par_defaut_premiere_etape(self):
        steps = parse_steps("let Depart = 1, Suite = 2 in Suite")
        self.assertEqual(source_expression(steps, ""), "1")

    def test_code_sans_let(self):
        self.assertEqual(parse_steps("Calendar.Create()"), [])
        self.assertEqual(source_expression([], "Calendar.Create()"), "Calendar.Create()")


COLONNES = """table Ventes

\tcolumn Montant
\t\tdataType: double
\t\tsourceColumn: Montant
\t\tsummarizeBy: sum

\tcolumn Marge = [Montant] - [Cout]
\t\tdataType: double
\t\tlineageTag: abc-123

\tcolumn 'Année civile' =
\t\t\tYEAR(
\t\t\t    Ventes[Date]
\t\t\t)
\t\tdataType: int64
\t\tisDataTypeInferred

\tcolumn Statut = ```
\t\t\tSWITCH(TRUE(), [Marge] > 0, "Positive", "Negative")
\t\t\t```
\t\tdataType: string

\t\tannotation SummarizationSetBy = Automatic
"""


class CalculatedColumnTest(unittest.TestCase):
    """Colonnes calculées : les blocs `column <nom> = <expression DAX>`."""

    def setUp(self):
        self.columns = {c.name: c.expression for c in extract_calculated_columns(COLONNES)}

    def test_colonne_ordinaire_ignoree(self):
        # `Montant` vient de la source : elle n'a pas d'expression à documenter
        self.assertNotIn("Montant", self.columns)

    def test_toutes_les_colonnes_calculees_sont_trouvees(self):
        self.assertEqual(sorted(self.columns), ["Année civile", "Marge", "Statut"])

    def test_expression_inline(self):
        self.assertEqual(self.columns["Marge"], "[Montant] - [Cout]")

    def test_expression_multi_lignes_sans_backticks(self):
        self.assertEqual(self.columns["Année civile"], "YEAR(\n    Ventes[Date]\n)")

    def test_expression_entre_backticks(self):
        self.assertEqual(
            self.columns["Statut"], 'SWITCH(TRUE(), [Marge] > 0, "Positive", "Negative")'
        )

    def test_colonnes_rattachees_a_la_table(self):
        table = parse_table(COLONNES)
        self.assertEqual(
            [c.name for c in table.calculated_columns], ["Marge", "Année civile", "Statut"]
        )

    def test_table_sans_colonne_calculee(self):
        self.assertEqual(extract_calculated_columns(VENTES), [])


if __name__ == "__main__":
    unittest.main()
