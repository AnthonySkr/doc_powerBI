"""
Le plan évolue au-dessus d'une documentation déjà rédigée.

Le contrat vérifié ici : une rubrique ajoutée au YAML atteint aussi les
éléments déjà documentés, à sa place dans le plan, sans rien déranger de ce que
l'utilisateur avait écrit — et sans défaire l'ordre qu'il s'était donné.
"""

import copy
import unittest

from docx import Document
from docx.oxml.ns import qn

from tests.test_merge_cycle import PLAN, MergeHarness, measure_section


class PlanEvolutionTest(MergeHarness):
    def plan(self, mutate) -> dict:
        plan = copy.deepcopy(PLAN)
        mutate(measure_section(plan))
        return {"sections": plan["sections"]}

    # ── Un bloc ajouté au plan ────────────────────────────────────
    def test_bloc_ajoute_apparait_dans_un_element_existant(self):
        self.generate(marge="SUM(T[a])")
        added = self.plan(
            lambda section: section["blocks"].insert(
                1, {"type": "user_fill", "id": "impact", "label": "Impact métier"}
            )
        )
        self.generate(added, marge="SUM(T[a])")
        self.assertIn("Impact métier", self.texts())

    def test_bloc_ajoute_prend_sa_place_dans_le_plan(self):
        self.generate(marge="SUM(T[a])")
        added = self.plan(
            lambda section: section["blocks"].insert(
                1, {"type": "user_fill", "id": "impact", "label": "Impact métier"}
            )
        )
        self.generate(added, marge="SUM(T[a])")
        layout = self.layout()
        self.assertEqual(layout.index("Impact métier"), layout.index("Code DAX") + 2)

    def test_bloc_ajoute_ne_derange_pas_la_redaction(self):
        self.generate(marge="SUM(T[a])")
        self.rewrite("[À compléter]", "Ce que je pense de cette mesure")
        added = self.plan(
            lambda section: section["blocks"].insert(
                1, {"type": "user_fill", "id": "impact", "label": "Impact métier"}
            )
        )
        self.generate(added, marge="SUM(T[a])")
        self.assertIn("Ce que je pense de cette mesure", self.texts())

    def test_sous_partie_ajoutee_apparait(self):
        """Une sous-partie sans `bookmark:` est repérée par son titre."""
        self.generate(marge="SUM(T[a])")
        added = self.plan(
            lambda section: section.update(
                sections=[
                    {
                        "title": "Limites connues",
                        "level": 4,
                        "blocks": [{"type": "user_fill", "id": "limites"}],
                    }
                ]
            )
        )
        self.generate(added, marge="SUM(T[a])")
        self.assertIn("Limites connues", self.texts())

    # ── Un bloc retiré du plan ────────────────────────────────────
    def test_bloc_retire_du_plan_rend_ce_qui_a_ete_ecrit_dedans(self):
        self.generate(marge="SUM(T[a])")
        self.write_under_table("Ce tableau se lit de gauche à droite")
        removed = self.plan(
            lambda section: section.update(
                blocks=[block for block in section["blocks"] if block["id"] != "champs"]
            )
        )
        self.generate(removed, marge="SUM(T[a])")
        texts = self.texts()
        self.assertIn("Ce tableau se lit de gauche à droite", texts)
        self.assertNotIn("Champs", texts)

    # ── L'ordre de l'utilisateur ──────────────────────────────────
    def test_ordre_de_l_utilisateur_respecte(self):
        """Un contenu du script déplacé à la main reste où l'utilisateur l'a mis."""
        self.generate(marge="SUM(T[a])")
        self.move_block_to_end("code")
        before = self.layout()
        self.generate(marge="SUM(T[a])")
        self.assertEqual(self.layout(), before)

    def test_bloc_ajoute_apres_un_deplacement(self):
        """Le plan complète un ordre remanié sans le défaire."""
        self.generate(marge="SUM(T[a])")
        self.move_block_to_end("code")
        added = self.plan(
            lambda section: section["blocks"].append(
                {"type": "user_fill", "id": "impact", "label": "Impact métier"}
            )
        )
        self.generate(added, marge="SUM(T[a])")
        layout = self.layout()
        self.assertIn("Impact métier", layout)
        self.assertGreater(layout.index("Code DAX"), layout.index("Sources"))

    # ── Les amorces ───────────────────────────────────────────────
    def test_amorce_jamais_touchee_suit_le_plan(self):
        """Une formulation améliorée dans le YAML atteint les documents existants."""
        self.generate(marge="SUM(T[a])")
        reworded = self.plan(
            lambda section: section["blocks"].__setitem__(
                3, {"type": "user_fill", "id": "commentaire", "label": "Lecture de la mesure"}
            )
        )
        self.generate(reworded, marge="SUM(T[a])")
        self.assertIn("Lecture de la mesure", self.texts())

    def test_amorce_rediged_l_emporte_sur_le_plan(self):
        self.generate(marge="SUM(T[a])")
        self.rewrite("[À compléter]", "Ma lecture de la mesure")
        reworded = self.plan(
            lambda section: section["blocks"].__setitem__(
                3, {"type": "user_fill", "id": "commentaire", "label": "Lecture de la mesure"}
            )
        )
        self.generate(reworded, marge="SUM(T[a])")
        texts = self.texts()
        self.assertIn("Ma lecture de la mesure", texts)
        self.assertNotIn("[À compléter]", texts)

    # ── Stabilité ─────────────────────────────────────────────────
    def test_document_stable_apres_evolution_du_plan(self):
        self.generate(marge="SUM(T[a])")
        self.rewrite("[À compléter]", "Ma lecture")
        added = self.plan(
            lambda section: section["blocks"].insert(
                1, {"type": "user_fill", "id": "impact", "label": "Impact métier"}
            )
        )
        self.generate(added, marge="SUM(T[a])")
        first = self.layout()
        self.generate(added, marge="SUM(T[a])")
        self.assertEqual(self.layout(), first)

    # ── Utilitaire ────────────────────────────────────────────────
    def move_block_to_end(self, block_id: str) -> None:
        """Déplace un contenu du script à la fin de son élément, comme dans Word."""
        document = Document(self.path)
        body = document.element.body
        nodes = list(body)

        start = next(
            index
            for index, node in enumerate(nodes)
            if node.tag == qn("w:p") and node.xpath("string(.)") == f"pbi::gen|{block_id}"
        )
        end = next(
            index
            for index in range(start + 1, len(nodes))
            if nodes[index].tag == qn("w:p")
            and nodes[index].xpath("string(.)").startswith("pbi::endgen")
        )
        moved = nodes[start : end + 1]

        # Fin de l'élément : l'ancre suivante, ou la fin du corps.
        stop = next(
            (
                nodes[index]
                for index in range(end + 1, len(nodes))
                if nodes[index].tag == qn("w:p")
                and nodes[index].xpath("string(.)").startswith("pbi::elem")
            ),
            body.find(qn("w:sectPr")),
        )
        for node in moved:
            body.remove(node)
        for node in moved:
            if stop is not None:
                stop.addprevious(node)
            else:
                body.append(node)
        document.save(self.path)


if __name__ == "__main__":
    unittest.main()
