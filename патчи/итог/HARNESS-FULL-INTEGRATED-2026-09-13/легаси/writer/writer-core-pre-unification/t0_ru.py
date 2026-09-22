"""T0 deterministic Russian linguistic layer: razdel + pymorphy3 + v0.3 registries.

Produces per-sentence signals used to build LinguisticDigest (skeleton v0.3).

Design notes (m2_t0):
- Every heuristic below is deterministic. Where the v0.3 lexicon has no entry
  (e.g. "доказывают", "вызывает", "дальнейшее увеличение", bare scope NP),
  we add an explicit regex heuristic; digest_builder records it in
  issue.details["heuristic"] so downstream tiers can distinguish registry-backed
  signals from T0 heuristics.
- Fail-closed: empty/whitespace/short input yields an empty T0Sentence, never an
  exception. Uses pymorphy3 (NOT pymorphy2, which is broken on Python 3.12).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:
    from razdel import sentenize, tokenize
except ImportError:  # minimal deterministic fallback for dependency-light RTT checks
    @dataclass(frozen=True)
    class _Segment:
        text: str
        start: int
        stop: int

    def sentenize(text: str):
        for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text):
            yield _Segment(match.group(0), match.start(), match.end())

    def tokenize(text: str):
        for match in re.finditer(r"\w+|[^\w\s]", text, re.UNICODE):
            yield _Segment(match.group(0), match.start(), match.end())

from registry_loader import get_registries

try:
    from pymorphy3 import MorphAnalyzer
except Exception:  # pragma: no cover
    MorphAnalyzer = None  # type: ignore

_MORPH = MorphAnalyzer() if MorphAnalyzer else None

# modality strength ordering (epistemic_force -> rank)
_FORCE_RANK = {
    "OBSERVED": 1,
    "CONSISTENT_WITH": 2,
    "POSSIBLE_INTERPRETATION": 3,
    "WEAK_INFERENCE": 4,
    "ESTABLISHED_WITHIN_SCOPE": 5,
    "CAUSAL_ASSERTED": 6,
    "BOOSTED": 7,
}

_SCOPE_RESTRICTORS = re.compile(
    r"\b(для\s+исследованных|в\s+исследованном\s+диапазоне|на\s+исследованных|"
    r"в\s+пределах|в\s+диапазоне|не\s+во\s+всех|только\s+для|"
    r"при\s+исследованных|в\s+условиях|для\s+рассмотренных|"
    r"в\s+части|в\s+ряде|отдельные|часть\s+образцов)\b",
    re.IGNORECASE,
)
_STRONG_ASSERT = re.compile(
    r"\b(доказыва\w+|подтвержда\w+|устанавлива\w+|гарантиру\w+|"
    r"несомненно|очевидно|безусловно|достоверно)\b",
    re.IGNORECASE,
)
_NEG_QUANT_EQ = re.compile(r"\b(не\s+во\s+всех|в\s+части|некоторых|в\s+ряде)\b", re.IGNORECASE)
_QUANTIFIER_UNIVERSAL = re.compile(r"\b(все|каждый|любой|всегда|универсальн\w+)\b", re.IGNORECASE)
_QUANTIFIER_EXIST = re.compile(r"\b(некоторые|некоторых|часть|отдельные|в\s+ряде)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(не|ни|без|отсутств\w+)\b", re.IGNORECASE)
_QUALIFIERS = re.compile(r"\b(возможно|вероятно|по-видимому|может|как\s+правило|"
                         r"в\s+основном|предположительно|по\s+всей\s+видимости)\b", re.IGNORECASE)
_CAUSAL_MARKERS = re.compile(r"\b(приводит\s+к|вызывает|обусловлено|обуславливает|"
                             r"вследствие|вызвано|является\s+причиной)\b", re.IGNORECASE)
# non-capturing unit group so findall returns full "number unit" strings, not units
_NUMERIC = re.compile(r"\b\d+[.,]?\d*\s*(?:%|°С|°C|нм|мкм|мм|МПа|ч|мин|с|ат\.?)?\b",
                      re.IGNORECASE)

# ---- m2_t0 heuristics (fixture-driven, see golden_traps.yaml) ----

# PRESUPPOSITION_CANDIDATE: "дальнейшее увеличение" presupposes a prior increase;
# "продолжает расти", "повторно", "по-прежнему", "вновь" likewise signal
# continuation/repetition of an established state.
_PRESUPPOSE = re.compile(
    r"\b("
    r"дальнейш\w+\s+(?:увеличени\w+|рост\w*|повышени\w+|возрастани\w+|"
    r"снижени\w+|уменьшени\w+|изменени\w+|ухудшени\w+|улучшени\w+)"
    r"|продолжа\w+\s+(?:увеличива\w+|раст\w+|повыша\w+|снижа\w+)"
    r"|повторн\w+|по-прежнему|вновь|ещ[её]\s+раз"
    r")\b",
    re.IGNORECASE,
)

# SCOPE_EXPANSION: "для <NP>" / "на <NP>" scope whose head NP is NOT marked as
# researched/tested (no "исследованных/рассмотренных/..." attributive) and is not
# a purpose/locative phrase. The researched-marked source (SCOPE_01) is safe.
_SCOPE_HEAD = re.compile(r"\b(?:для|на)\s+([а-яёa-z0-9]+)", re.IGNORECASE)
# NOTE: suffix is \w* (not \w+) so BOTH adjectival (нн: "исследованные") and
# nominal (н: "исследования") forms are matched. The bare noun "исследования"
# is itself a research marker, not an un-restricted scope.
_SCOPE_ATTR_RESEARCH = re.compile(
    r"\b(?:исследован\w*|рассмотрен\w*|изучен\w*|проанализирован\w*|"
    r"протестирован\w*|испытан\w*|экспериментальн\w*|тестирован\w*)\b",
    re.IGNORECASE,
)
_SCOPE_EXCLUDED_HEADS = frozenset({
    # purpose gerunds ("для расчёта/оценки/...") — not scope expansions
    "расчет", "расчёта", "расчета", "оценки", "оценку", "определения",
    "определению", "анализа", "анализу", "получения", "получению",
    "сравнения", "сравнению", "построения", "построению", "моделирования",
    "моделированию", "описания", "реализации", "достижения", "вычисления",
    "вычислений", "измерения", "измерений", "регистрации", "контроля",
    "проверки", "проверку",
    # research nouns used as purpose gerunds ("для исследования/изучения...")
    "исследования", "исследование", "изучения", "изучение",
    "рассмотрения", "рассмотрение", "испытания", "испытание",
    # locative/illustrative heads ("на рисунке/графике/...")
    "рисунке", "графике", "таблице", "схеме", "диаграмме", "изображении",
    "карте",
    # deictic fillers
    "этого", "этой", "нас", "себя", "чего",
})

# QUALIFIER_LOSS: an unhedged medium-strong (ESTABLISHED..CAUSAL_ASSERTED)
# non-causal claim with no evidence-framing verb.
_EVIDENCE_FRAME = re.compile(
    r"\b(наблюда\w+|свидетельств\w+|согласу\w+|подтвержда\w+|показыва\w+|указыва\w+)\b",
    re.IGNORECASE,
)


@dataclass
class T0Sentence:
    text: str
    tokens: list[str] = field(default_factory=list)
    lemmas: list[str] = field(default_factory=list)
    force: str = "OBSERVED"
    force_expr: str = ""
    causal: bool = False
    negation: bool = False
    scope_restricted: bool = False
    qualifiers: list[str] = field(default_factory=list)
    universals: list[str] = field(default_factory=list)
    connectives: list[dict[str, Any]] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    # ---- m2_t0 risk signals (deterministic, registry-backed where possible) ----
    presuppositions: list[str] = field(default_factory=list)
    modality_upgrade: bool = False
    causality_upgrade: bool = False
    scope_expansion: bool = False
    scope_expansion_head: str = ""
    reformulation_drift: bool = False
    qualifier_loss: bool = False

    @property
    def force_rank(self) -> int:
        return _FORCE_RANK.get(self.force, 0)


def _detect_scope_expansion(low: str) -> tuple[bool, str]:
    """True if a "для/на <NP>" scope phrase has no research attributive.

    Window covers ~60 chars before / 100 after the phrase so attributive
    adjectives on either side of the head noun are seen.
    """
    for m in _SCOPE_HEAD.finditer(low):
        head = m.group(1)
        if head in _SCOPE_EXCLUDED_HEADS:
            continue
        window = low[max(0, m.start() - 60): m.start() + 100]
        if _SCOPE_ATTR_RESEARCH.search(window):
            continue
        return True, head
    return False, ""


def _detect_reformulation_drift(s: T0Sentence) -> bool:
    """REFORMULATION connective ("иными словами") re-states with universalized
    or upgraded force -> drift (fixture REFORM_01)."""
    reform = [
        c for c in s.connectives
        if c.get("relation") == "REFORMULATION" or c.get("requires_semantic_equivalence")
    ]
    if not reform:
        return False
    return bool(s.universals) or s.force_rank >= _FORCE_RANK["CAUSAL_ASSERTED"]


def analyze_sentence(text: str) -> T0Sentence:
    r = get_registries()
    if text is None:
        text = ""
    s = T0Sentence(text=text.strip())
    s.tokens = [t.text for t in tokenize(text)]
    if _MORPH:
        for t in s.tokens:
            parsed = _MORPH.parse(t)
            s.lemmas.append(parsed[0].normal_form if parsed else t)

    low = text.lower()

    # epistemic force from lexicon (longest matching expr with epistemic_force)
    best_expr, best_force = "", ""
    for expr, info in r.expr_force.items():
        force = info.get("epistemic_force")
        if force and expr in low and len(expr) > len(best_expr):
            best_expr, best_force = expr, force
    # strong assertive verbs fallback (not covered by registry)
    if _STRONG_ASSERT.search(low):
        if not best_force or _FORCE_RANK.get(best_force, 0) < _FORCE_RANK["BOOSTED"]:
            best_force = "BOOSTED"
    s.force_expr = best_expr
    s.force = best_force or "OBSERVED"

    s.causal = bool(_CAUSAL_MARKERS.search(low))
    s.negation = bool(_NEGATION.search(low))
    s.scope_restricted = bool(_SCOPE_RESTRICTORS.search(low))
    s.qualifiers = _QUALIFIERS.findall(low)
    s.universals = _QUANTIFIER_UNIVERSAL.findall(low)
    s.numbers = [n for n in _NUMERIC.findall(text) if n.strip()]

    for conn, info in r.connective_rel.items():
        if conn in low:
            s.connectives.append({
                "form": conn,
                "relation": info.get("relation"),
                "requires_argument_support": info.get("requires_argument_support", False),
                "requires_semantic_equivalence": info.get("requires_semantic_equivalence", False),
            })

    # ---- T0 risk heuristics (m2_t0) ----
    s.presuppositions = _PRESUPPOSE.findall(low)
    s.modality_upgrade = s.force == "BOOSTED" and not s.qualifiers
    s.causality_upgrade = bool(s.causal and not s.qualifiers and not s.presuppositions)
    s.scope_expansion, s.scope_expansion_head = _detect_scope_expansion(low)
    s.reformulation_drift = _detect_reformulation_drift(s)
    s.qualifier_loss = bool(
        _FORCE_RANK.get(s.force, 0) in (5, 6)
        and not s.qualifiers
        and not s.causal
        and not s.scope_restricted
        and not s.presuppositions
        and not _EVIDENCE_FRAME.search(low)
    )
    return s


def split_sentences(text: str) -> list[str]:
    return [s.text.strip() for s in sentenize(text) if s.text.strip()]


def build_scope_field(s: T0Sentence) -> dict[str, Any]:
    """Scope structure per LinguisticDigest schema (dict payload)."""
    scope: dict[str, Any] = {"restricted": s.scope_restricted}
    if s.scope_restricted:
        scope["type"] = "observed_set"
    if s.universals and not s.scope_restricted:
        scope["type"] = "universal"
        scope["risk"] = "SCOPE_EXPANSION"
    if s.negation:
        scope["negation"] = True
    if s.numbers:
        scope["numeric_mentions"] = s.numbers[:5]
    return scope
