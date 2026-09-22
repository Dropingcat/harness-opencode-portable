from __future__ import annotations

import unittest

from researcher_core.formulas import check_constant, detect_formula, list_formulas


class FormulasAdapterTests(unittest.TestCase):
    def test_detect_formula_scherrer_variants(self) -> None:
        self.assertEqual(detect_formula("Scherrer equation with βcosθ"), "scherrer")
        self.assertEqual(detect_formula("формула Шеррера"), "scherrer")
        self.assertEqual(detect_formula("W-H method"), "williamson_hall")
        self.assertEqual(detect_formula("плотность дислокаций ρ ="), "dislocation")
        self.assertEqual(detect_formula("Arrhenius exp(-Ea/(RT))"), "arrhenius")
        self.assertIsNone(detect_formula("no formula here"))

    def test_check_constant_scherrer(self) -> None:
        self.assertEqual(check_constant("scherrer", "K=0.9 used"), "formula_consistent")
        self.assertEqual(check_constant("scherrer", "K=1.0 alternative"), "formula_conflict")
        self.assertEqual(check_constant("scherrer", "K=1 present"), "formula_conflict")
        self.assertEqual(check_constant("scherrer", "no constant"), "unknown")
        self.assertEqual(check_constant("arrhenius", "arrhenius text"), "formula_consistent")
        self.assertEqual(check_constant("arrhenius", "other"), "unknown")

    def test_list_formulas(self) -> None:
        self.assertIn("scherrer", list_formulas())
        self.assertIn("arrhenius", list_formulas())


if __name__ == "__main__":
    unittest.main()
