#!/usr/bin/env python3
"""test_circularity.py — реальные тесты детектора циркулярности.

Проверяют на реальных данных «Актуальности» (input_actuality.txt):
  - C3: источники S3-S5 (реконструкция строк документа) → document_derived;
  - внешний источник (например, реальный открытый абстракт) → external;
  - in_text_reconstruction → document_derived по построению.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from circularity import detect_origin, annotate_source, phrase_coverage

ACTUALITY_DOC = Path("/tmp/abstract_test/compare/input_actuality.txt")
DOC_TEXT = ACTUALITY_DOC.read_text(encoding="utf-8") if ACTUALITY_DOC.is_file() else ""

C3_CLAIM = ("Наблюдается ускорение образования нитридных фаз при комбинированных "
            "воздействиях — лазерная обработка и вакуумное азотирование, "
            "механическая обработка и вакуумное азотирование.")

# S3/S4/S5 — реконструкции строк 5-6 документа (см. sources.json C3)
S3_SCHAAF = "П. Шааф — лазерное азотирование железа с анализом механизмов ускорения насыщения."
S5_MAKAROV = ("Показано ускорение структурообразования при комбинированных воздействиях, "
              "однако эксперименты фиксируют ускорение процесса образования нитридных фаз, "
              "но не связывают его количественно с параметрами неоднородных микродеформаций.")

# Реальный внешний источник (ScienceDirect, найден через DDG)
EXTERNAL_EN = ("In this study, we demonstrated that irradiating austenitic steel with a "
               "nanosecond pulsed laser beam in an open atmosphere leads to the formation "
               "of a hard nitride layer. The wear resistance was improved.")


def test_c3_s5_is_document_derived():
    """S5 (пересказ строки 5 документа) → document_derived."""
    res = detect_origin(S5_MAKAROV, C3_CLAIM, DOC_TEXT)
    assert res["origin"] == "document_derived"
    assert "source_paraphrases_document" in res["markers"]


def test_c3_s3_is_document_derived_with_doc():
    """S3 (реконструкция строки 5) при наличии документа → document_derived."""
    res = detect_origin(S3_SCHAAF, C3_CLAIM, DOC_TEXT)
    # S3 — пересказ строки документа, где упоминается П. Шааф
    assert res["origin"] == "document_derived"


def test_in_text_reconstruction_always_derived():
    """found_via=in_text_reconstruction → document_derived по построению."""
    res = detect_origin("Любой текст источника", C3_CLAIM, found_via="in_text_reconstruction")
    assert res["origin"] == "document_derived"
    assert "in_text_reconstruction" in res["markers"]


def test_external_english_source_is_external():
    """Реальный внешний источник (английский абстракт) → external."""
    res = detect_origin(EXTERNAL_EN, C3_CLAIM, DOC_TEXT)
    assert res["origin"] == "external"
    assert res["markers"][-1] == "external"


def test_claim_verbatim_in_source_is_derived():
    """Claim дословно входит в источник → document_derived (сильный сигнал)."""
    source = f"Авторы показали, что: {C3_CLAIM}. Это подтверждает выводы."
    res = detect_origin(source, C3_CLAIM)
    assert res["origin"] == "document_derived"
    assert "claim_is_substring_of_source" in res["markers"]


def test_annotate_source_adds_caveat():
    """annotate_source добавляет origin + caveat circular_source для документных."""
    src = {"title": "S5", "excerpt": S5_MAKAROV, "found_via": "local_corpus"}
    annotate_source(src, C3_CLAIM, DOC_TEXT)
    assert src["origin"] == "document_derived"
    texts = [c.get("text", "") for c in src.get("caveats", [])]
    assert any("circular_source" in t for t in texts)


def test_phrase_coverage_works():
    """Покрытие биграммами считает реальные пересечения."""
    cov = phrase_coverage("ускорение нитридных фаз", "ускорение нитридных фаз при комбинированных")
    assert cov > 0.5


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))