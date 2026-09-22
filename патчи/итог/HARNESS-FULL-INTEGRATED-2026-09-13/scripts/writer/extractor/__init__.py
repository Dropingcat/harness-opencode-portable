"""Deterministic writer extractor (ported from writer-core legacy src_skeleton/extractor).

Чистые stdlib модули (без pymupdf / pymorphy2 / LLM / c1_c2_structure):
  - claim_qa:         span_locate (абсолютные/относительные координаты claim), classify_claim
  - extraction_engine: детерминированный слой A-D (claims с start/end, objects, discourse, style)
  - graph_builder:    claims/objects/филология -> узлы/рёбра 12 графов (rel_pos + abs_span)
  - context_analyzer: окрестности span (context_before/after), решение по окружению
  - c5_number:        извлечение quantity (value+unit+dimension) с позицией

Перенесено 2026-09-06 из writer-core (legacy_sources) в HARNESS scripts/writer/extractor.
Принцип: LLM ПРЕДЛАГАЕТ, код ПРИНИМАЕТ/ОТКЛОНЯЕТ (span grounding).
"""

from .claim_qa import classify_claim, span_grounded, span_locate, qa_claims, qa_objects
from .c5_number import extract_quantities, extract_from_sentences
from .extraction_engine import extract_all, ExtractionResult, _split_sentences
from .graph_builder import build_graphs, GNode, GEdge
from .context_analyzer import get_context, has_marker_in_window, is_rhetorical_repetition

__all__ = [
    "classify_claim", "span_grounded", "span_locate", "qa_claims", "qa_objects",
    "extract_quantities", "extract_from_sentences",
    "extract_all", "ExtractionResult", "_split_sentences",
    "build_graphs", "GNode", "GEdge",
    "get_context", "has_marker_in_window", "is_rhetorical_repetition",
]
