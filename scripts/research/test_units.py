import math

import pytest

from units import convert, dimension, normalize_unit


def test_normalize_uppercase():
    assert normalize_unit("HV") == "hv"
    assert normalize_unit("GPa") == "gpa"


def test_convert_hv_to_gpa():
    assert convert(824, "hv", "gpa") == pytest.approx(8.080968, rel=1e-3)


def test_convert_celsius_to_kelvin():
    assert convert(540, "celsius", "kelvin") == 813.15


def test_convert_kelvin_to_celsius():
    assert convert(813.15, "kelvin", "celsius") == pytest.approx(540)


def test_convert_cm2_per_s_to_m2_per_s():
    assert convert(1, "cm2_per_s", "m2_per_s") == 0.0001


def test_dimension_mismatch():
    assert dimension("hv") != dimension("celsius")


def test_unsupported_conversion():
    with pytest.raises(ValueError):
        convert(1, "hv", "kelvin")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
