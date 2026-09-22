from formulas import detect_formula, check_constant


def test_detect_scherrer_ru():
    assert detect_formula("средний размер кристаллита по Шерреру") == "scherrer"


def test_detect_scherrer_formula():
    assert detect_formula("D = 0.9λ/(βcosθ)") == "scherrer"


def test_detect_williamson_hall():
    assert detect_formula("метод Williamson-Hall для микронапряжений") == "williamson_hall"


def test_detect_dislocation():
    assert detect_formula("плотность дислокаций ρ") == "dislocation"


def test_detect_arrhenius():
    assert detect_formula("по уравнению Аррениуса") == "arrhenius"


def test_detect_none():
    assert detect_formula("обычный текст без формул") is None


def test_check_constant_conflict():
    assert check_constant("scherrer", "K=1, D=λ/(βcosθ)") == "formula_conflict"


def test_check_constant_consistent():
    assert check_constant("scherrer", "K=0.9, D=0.9λ/(βcosθ)") == "formula_consistent"


def test_check_constant_arrhenius():
    assert check_constant("arrhenius", "по уравнению Аррениуса") == "formula_consistent"
