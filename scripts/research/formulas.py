FORMULA_MARKERS: dict[str, dict] = {
    "scherrer": {
        "patterns": ["scherrer", "шеррер", "шенер", "βcosθ"],
        "constants": {"K": {"canonical": 0.9, "alternative": 1.0}},
    },
    "williamson_hall": {
        "patterns": ["williamson-hall", "уильямсон-холл", "w-h"],
        "constants": {},
    },
    "dislocation": {
        "patterns": ["дислокац", "ρ =", "rho", "плотность дислокаций"],
        "constants": {},
    },
    "arrhenius": {
        "patterns": ["аррениус", "arrhenius", "exp(-ea/(rt))"],
        "constants": {},
    },
}


def detect_formula(text: str) -> str | None:
    lowered = text.lower()
    for name, info in FORMULA_MARKERS.items():
        for pattern in info["patterns"]:
            if pattern.lower() in lowered:
                return name
    return None


def check_constant(formula_name: str, text: str) -> str:
    if formula_name == "scherrer":
        if "0.9" in text:
            return "formula_consistent"
        if "1.0" in text or "K=1" in text:
            return "formula_conflict"
        return "unknown"
    if detect_formula(text) == formula_name:
        return "formula_consistent"
    return "unknown"
