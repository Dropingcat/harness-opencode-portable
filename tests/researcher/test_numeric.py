from __future__ import annotations

import unittest
from decimal import Decimal

from researcher_core.numeric import NumericComparisonStatus, NumericValue, compare_numeric, convert, dimension, normalize_unit


class NumericUnitTests(unittest.TestCase):
    def test_unit_aliases_normalize_to_canonical_units(self) -> None:
        self.assertEqual(normalize_unit("%"), "percent")
        self.assertEqual(normalize_unit("µm"), "um")
        self.assertEqual(normalize_unit("μm"), "um")
        self.assertEqual(normalize_unit("Å"), "angstrom")
        self.assertEqual(normalize_unit("kJ mol^-1"), "kj/mol")
        self.assertEqual(normalize_unit("HV"), "hv")
        self.assertEqual(dimension("MPa"), "pressure")

    def test_convert_length_nm_to_um(self) -> None:
        self.assertEqual(convert(Decimal("1000"), "nm", "um"), Decimal("1"))
        self.assertEqual(convert(Decimal("1"), "um", "nm"), Decimal("1000"))

    def test_convert_kj_per_mol_to_ev_per_atom(self) -> None:
        self.assertEqual(convert(Decimal("96.4853321233100184"), "kJ/mol", "eV/atom"), Decimal("1"))
        self.assertEqual(convert(Decimal("1"), "eV/atom", "kJ/mol"), Decimal("96.4853321233100184"))

    def test_convert_celsius_to_kelvin(self) -> None:
        self.assertEqual(convert(Decimal("25"), "celsius", "kelvin"), Decimal("298.15"))
        self.assertEqual(convert(Decimal("273.15"), "kelvin", "celsius"), Decimal("0"))

    def test_convert_percent_to_ratio(self) -> None:
        self.assertEqual(convert(Decimal("25"), "percent", "ratio"), Decimal("0.25"))


class NumericComparisonTests(unittest.TestCase):
    def test_dimension_mismatch_is_not_comparable(self) -> None:
        result = compare_numeric(NumericValue(value="1", unit="m"), NumericValue(value="1", unit="kelvin"))

        self.assertEqual(result.status, NumericComparisonStatus.NOT_COMPARABLE)
        self.assertIn("dimension mismatch", result.reason)

    def test_exact_converted_values_match(self) -> None:
        result = compare_numeric(NumericValue(value="1000", unit="nm"), NumericValue(value="1", unit="um"))

        self.assertEqual(result.status, NumericComparisonStatus.MATCH)
        self.assertEqual(result.difference, Decimal("0"))

    def test_converted_values_mismatch_outside_tolerance(self) -> None:
        result = compare_numeric(
            NumericValue(value="1000", unit="nm"),
            NumericValue(value="2", unit="um"),
            tolerance_relative="0.01",
        )

        self.assertEqual(result.status, NumericComparisonStatus.MISMATCH)

    def test_overlapping_ranges_are_partial_overlap(self) -> None:
        result = compare_numeric(
            NumericValue(lower="1", upper="3", unit="m"),
            NumericValue(lower="2", upper="4", unit="m"),
        )

        self.assertEqual(result.status, NumericComparisonStatus.PARTIAL_OVERLAP)

    def test_scalar_inside_converted_range_matches(self) -> None:
        result = compare_numeric(
            NumericValue(value="1500", unit="nm"),
            NumericValue(lower="1", upper="2", unit="um"),
        )

        self.assertEqual(result.status, NumericComparisonStatus.MATCH)


if __name__ == "__main__":
    unittest.main()
