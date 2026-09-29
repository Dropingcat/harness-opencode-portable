# -*- coding: utf-8 -*-
"""Тесты V-1 System Health Monitor."""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from health_monitor import (HealthMonitor, GoldenCorpusComparator, MetricTrendDetector,
                            PhysicsValidator, HistoricalComparator, ExternalObserver,
                            ReanimationProtocol, DriftSignal, HealthStatus)


def test_golden_comparator_ok():
    c = GoldenCorpusComparator(threshold=0.0)  # порог 0 = всегда OK
    s = c.compare("some text")
    assert s.severity == "OK"


def test_golden_comparator_empty():
    c = GoldenCorpusComparator()
    s = c.compare("text")
    assert s.severity == "OK"  # пустой корпус = OK (не ложная тревога)


def test_trend_detector_insufficient():
    d = MetricTrendDetector()
    assert d.detect_trend().severity == "OK"  # <5 точек


def test_trend_detector_filler_grows():
    d = MetricTrendDetector()
    # filler_word_ratio растёт → деградация
    for i in range(8):
        d.record({"filler_word_ratio": 0.1 + i * 0.05,
                  "avg_sentence_length": 20, "terminology_density": 0.5,
                  "citation_per_claim": 2.0})
    s = d.detect_trend()
    assert s.severity == "WARNING"
    assert "filler_word_ratio" in s.metrics


def test_trend_detector_ok_when_stable():
    d = MetricTrendDetector()
    for _ in range(8):
        d.record({"filler_word_ratio": 0.1, "avg_sentence_length": 20,
                  "terminology_density": 0.5, "citation_per_claim": 2.0})
    assert d.detect_trend().severity == "OK"


def test_physics_validator_callback():
    def check(text):
        if "impossible" in text:
            return [{"type": "DIMENSIONAL_MISMATCH", "severity": "CRITICAL",
                     "message": "bad"}]
        return []
    p = PhysicsValidator(check_fn=check)
    assert p.validate("impossible claim").severity == "CRITICAL"
    assert p.validate("fine claim").severity == "OK"


def test_history_comparator_drop():
    h = HistoricalComparator(drop_threshold=0.1)
    h.history = {
        "texts": [],
        "metrics": [{"citation_per_claim": 2.0}] * 10,  # прошлое хорошее
    }
    s = h.compare_with_past({"citation_per_claim": 0.5})  # текущее плохое
    assert s.severity == "WARNING"


def test_observer_threshold():
    o = ExternalObserver(evaluate_fn=lambda t: {"fail_count": 3}, fail_threshold=2)
    assert o.evaluate("x").severity == "CRITICAL"


def test_health_aggregation():
    # 2 критических → BLOCK
    status = HealthStatus([
        DriftSignal("CRITICAL", "physics", action="BLOCK"),
        DriftSignal("CRITICAL", "golden", action="BLOCK"),
        DriftSignal("OK", "trend"),
    ])
    assert status.severity == "BLOCK"
    assert not status.can_generate


def test_veto_reanimation():
    reanim = ReanimationProtocol(
        find_last_good=lambda: {"policies": {"old": 1}, "tactics": [1, 2]},
        load_golden_policies=lambda: {"golden": True},
    )
    hm = HealthMonitor(reanimation=reanim)
    bad = HealthStatus([DriftSignal("CRITICAL", "physics"), DriftSignal("CRITICAL", "golden")])
    result = hm.apply_veto(bad)
    assert result is not None
    assert result["tactics"] == []  # тактики очищены
    assert result["policies"] == {"golden": True}  # политики из эталона


def test_monitor_pre_and_post():
    hm = HealthMonitor()  # все каналы по умолчанию (без корпуса/наблюдателя)
    assert hm.pre_generation_check().severity == "OK"
    assert hm.post_generation_check("some physics text").severity == "OK"
    assert hm.can_generate() is True


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)