from uncertainty import parse_uncertainty, values_in_range, compare_with_uncertainty


def test_parse_uncertainty_spaces():
    assert parse_uncertainty("77 ± 3") == (77.0, 3.0)


def test_parse_uncertainty_no_spaces():
    assert parse_uncertainty("0.42±0.03") == (0.42, 0.03)


def test_parse_uncertainty_decimal():
    assert parse_uncertainty("12.5 ± 0.5") == (12.5, 0.5)


def test_parse_uncertainty_no_uncertainty():
    assert parse_uncertainty("просто 5") is None


def test_values_in_range_overlap():
    assert values_in_range(77, 3, 75, 1) is True


def test_values_in_range_no_overlap():
    assert values_in_range(77, 3, 70, 1) is False


def test_compare_match():
    assert compare_with_uncertainty(77, 3, 78, 1) == "MATCH"


def test_compare_mismatch():
    assert compare_with_uncertainty(77, 3, 65, 1) == "MISMATCH"


def test_compare_no_data():
    assert compare_with_uncertainty(77, None, 78, None) == "NO_DATA"
