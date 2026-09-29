# -*- coding: utf-8 -*-
"""
health_monitor.py — V-1 System Health Monitor (внешняя сила над V1-V8).

Постоянный наблюдатель с правом вето. Не участвует в генерации,
но может остановить систему, откатить состояние или запустить реанимацию.

5 каналов мониторинга:
  1. GoldenCorpusComparator  — дрейф относительно эталона (реальные статьи)
  2. MetricTrendDetector     — тренд метрик в скользящем окне
  3. PhysicsValidator        — физическая консистентность (код, не LLM)
  4. HistoricalComparator    — сравнение с прошлыми выходами (N циклов назад)
  5. ExternalObserver        — независимый взгляд (отдельная LLM/человек)

Три уровня реакции: WARNING → BLOCK → EMERGENCY (реанимация).
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------- контракты

class DriftSignal:
    """Сигнал деградации от одного канала."""

    __slots__ = ("severity", "channel", "message", "action", "metrics")

    def __init__(self, severity: str, channel: str, message: str = "",
                 action: str = "", metrics: Optional[Dict[str, float]] = None) -> None:
        self.severity = severity      # OK | WARNING | CRITICAL
        self.channel = channel        # golden | trend | physics | history | observer
        self.message = message
        self.action = action          # BLOCK_GENERATION | ROLLBACK | REANIMATE | ...
        self.metrics = metrics or {}


class HealthStatus:
    """Совокупное здоровье системы."""

    __slots__ = ("severity", "signals", "checked_at", "can_generate")

    def __init__(self, signals: List[DriftSignal]) -> None:
        self.signals = signals
        self.checked_at = datetime.now().isoformat()
        # Агрегация: EMERGENCY(3+) > BLOCK(2) > WARNING(1) > OK
        critical = [s for s in signals if s.severity == "CRITICAL"]
        warning = [s for s in signals if s.severity == "WARNING"]
        if len(critical) >= 3:
            self.severity = "EMERGENCY"
        elif len(critical) >= 2:
            self.severity = "BLOCK"
        elif len(critical) == 1 or len(warning) >= 2:
            self.severity = "WARNING"
        else:
            self.severity = "OK"
        self.can_generate = self.severity in ("OK", "WARNING")


# ---------------------------------------------------------------- канал 1

class GoldenCorpusComparator:
    """Канал 1: дрейф относительно эталона (реальные научные статьи)."""

    def __init__(self, golden_corpus_path: Optional[str] = None,
                 threshold: float = 0.75,
                 embed_fn: Optional[Callable[[str], List[float]]] = None) -> None:
        self.threshold = threshold
        self.golden_embeddings: List[Dict[str, Any]] = []
        self._embed = embed_fn or self._default_embed
        if golden_corpus_path:
            self.load_corpus(golden_corpus_path)

    def load_corpus(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        if p.suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            for item in data:
                self.golden_embeddings.append({
                    "text": item.get("text", ""),
                    "embedding": item.get("embedding", self._embed(item.get("text", ""))),
                })
        else:  # txt: по абзацам
            text = p.read_text(encoding="utf-8")
            for para in [x.strip() for x in text.split("\n\n") if x.strip()]:
                self.golden_embeddings.append({"text": para, "embedding": self._embed(para)})

    @staticmethod
    def _default_embed(text: str) -> List[float]:
        """Фоллбэк: эмбеддинг на основе частотности слов (детерминированный).
        Для реального использования подставить sentence-трансформер."""
        import hashlib
        tokens = text.lower().split()
        vec = {}
        for t in tokens:
            h = int(hashlib.md5(t.encode()).hexdigest(), 16)
            vec[h % 512] = vec.get(h % 512, 0) + 1
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return [vec.get(i, 0) / norm for i in range(512)]

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    def compare(self, generated_text: str) -> DriftSignal:
        if not self.golden_embeddings:
            return DriftSignal("OK", "golden", "корпус пуст")
        gen = self._embed(generated_text)
        sims = [self._cosine(gen, g["embedding"]) for g in self.golden_embeddings]
        max_sim = max(sims)
        if max_sim < self.threshold:
            return DriftSignal(
                "CRITICAL", "golden",
                f"сходство с эталоном {max_sim:.2f} < {self.threshold}",
                "BLOCK_GENERATION", {"golden_similarity": max_sim},
            )
        return DriftSignal("OK", "golden", "", "", {"golden_similarity": max_sim})


# ---------------------------------------------------------------- канал 2

class MetricTrendDetector:
    """Канал 2: тренд метрик в скользящем окне (не мгновенные значения)."""

    def __init__(self, window_size: int = 20,
                 degrade_if: Optional[Dict[str, str]] = None) -> None:
        self.window_size = window_size
        self.history: List[Dict[str, float]] = []
        # degrade_if: {metric_name: "up"|"down"} — какое направление = деградация
        self.degrade_if = degrade_if or {
            "filler_word_ratio": "up",
            "avg_sentence_length": "up",
            "terminology_density": "down",
            "citation_per_claim": "down",
        }

    def record(self, metrics: Dict[str, float]) -> None:
        self.history.append(metrics)
        if len(self.history) > self.window_size:
            self.history.pop(0)

    @staticmethod
    def _slope(values: List[float]) -> float:
        n = len(values)
        if n < 2:
            return 0.0
        xs = list(range(n))
        mx = sum(xs) / n
        my = sum(values) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, values))
        den = sum((x - mx) ** 2 for x in xs)
        return num / den if den else 0.0

    def detect_trend(self) -> DriftSignal:
        if len(self.history) < 5:
            return DriftSignal("OK", "trend", "недостаточно данных")
        degradations = {}
        for metric, direction in self.degrade_if.items():
            vals = [m.get(metric, 0.0) for m in self.history]
            slope = self._slope(vals)
            # up: рост = плохо; down: падение = плохо
            bad = slope > 0.001 if direction == "up" else slope < -0.001
            if bad:
                degradations[metric] = round(slope, 4)
        if len(degradations) >= 1:
            return DriftSignal("WARNING", "trend",
                               f"тренды метрик ухудшаются: {degradations}",
                               "INCREASE_MONITORING", degradations)
        return DriftSignal("OK", "trend", "", "", degradations)


# ---------------------------------------------------------------- канал 3

class PhysicsValidator:
    """Канал 3: физическая консистентность (код, не LLM)."""

    def __init__(self, materials_db: Optional[Dict[str, Dict[str, float]]] = None,
                 check_fn: Optional[Callable[[str], List[Dict[str, Any]]]] = None) -> None:
        self.materials_db = materials_db or {}
        self._check = check_fn  # внешний код-валидатор (размерности/числа)

    def validate(self, text: str) -> DriftSignal:
        if self._check:
            errors = self._check(text)
            if errors:
                critical = [e for e in errors if e.get("severity") == "CRITICAL"]
                sev = "CRITICAL" if critical else "WARNING"
                return DriftSignal(sev, "physics", str(errors[:3]), "BLOCK_GENERATION")
        return DriftSignal("OK", "physics", "код-проверки не настроены")


# ---------------------------------------------------------------- канал 4

class HistoricalComparator:
    """Канал 4: сравнение с прошлыми выходами (N циклов назад)."""

    def __init__(self, history: Optional[Dict[str, List[Dict[str, float]]]] = None,
                 drop_threshold: float = 0.10) -> None:
        self.history = history or {"texts": [], "metrics": []}
        self.drop_threshold = drop_threshold

    def compare_with_past(self, current_metrics: Dict[str, float],
                          cycles_back: int = 10) -> DriftSignal:
        past = self.history.get("metrics", [])[-cycles_back:]
        if not past:
            return DriftSignal("OK", "history", "нет прошлых данных")
        degradation = {}
        for metric, cur in current_metrics.items():
            past_avg = sum(m.get(metric, 0.0) for m in past) / len(past)
            if past_avg and cur < past_avg * (1 - self.drop_threshold):
                drop = (past_avg - cur) / past_avg
                degradation[metric] = round(drop, 3)
        if degradation:
            return DriftSignal("WARNING", "history",
                               f"качество упало vs {cycles_back} циклов: {degradation}",
                               "ROLLBACK_TO_PREVIOUS_STATE", degradation)
        return DriftSignal("OK", "history", "", "", degradation)


# ---------------------------------------------------------------- канал 5

class ExternalObserver:
    """Канал 5: внешний наблюдатель (отдельная LLM/человек)."""

    def __init__(self, evaluate_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
                 fail_threshold: int = 2) -> None:
        self._evaluate = evaluate_fn
        self.fail_threshold = fail_threshold

    def evaluate(self, text: str) -> DriftSignal:
        if not self._evaluate:
            return DriftSignal("OK", "observer", "наблюдатель не настроен")
        report = self._evaluate(text)
        fail_count = report.get("fail_count", 0)
        if fail_count >= self.fail_threshold:
            return DriftSignal("CRITICAL", "observer",
                               f"внешний наблюдатель: {fail_count} нарушений",
                               "BLOCK_GENERATION_AND_ROLLBACK", {"fail_count": fail_count})
        return DriftSignal("OK", "observer", "", "", {"fail_count": fail_count})


# ---------------------------------------------------------------- реанимация

class ReanimationProtocol:
    """Процедура реанимации: откат к последнему хорошему состоянию."""

    def __init__(self, find_last_good: Callable[[], Dict[str, Any]],
                 load_golden_policies: Optional[Callable[[], Dict[str, Any]]] = None,
                 on_full_reset: Optional[Callable[[], Dict[str, Any]]] = None) -> None:
        self._find_last_good = find_last_good
        self._golden_policies = load_golden_policies or (lambda: {})
        self._full_reset = on_full_reset or self._default_reset

    @staticmethod
    def _default_reset() -> Dict[str, Any]:
        return {"tactics": [], "policies": {}, "prompt_templates": {}, "reset": True}

    def execute(self) -> Dict[str, Any]:
        """Вернуть последнее хорошее состояние (с очисткой тактик/политик)."""
        last_good = self._find_last_good()
        last_good["tactics"] = []
        last_good["policies"] = self._golden_policies()
        last_good["health_reset_at"] = datetime.now().isoformat()
        return last_good


# ---------------------------------------------------------------- фасад

class HealthMonitor:
    """V-1: фасад — запускает все каналы, агрегирует, решает (вето)."""

    def __init__(self, channels: Optional[Dict[str, Any]] = None,
                 reanimation: Optional[ReanimationProtocol] = None) -> None:
        self.channels = channels or {
            "golden": GoldenCorpusComparator(),
            "trend": MetricTrendDetector(),
            "physics": PhysicsValidator(),
            "history": HistoricalComparator(),
            "observer": ExternalObserver(),
        }
        self.reanimation = reanimation

    def pre_generation_check(self) -> HealthStatus:
        """Проверка ПЕРЕД генерацией: тренды + золотой корпус (если есть данные)."""
        signals = []
        trend = self.channels["trend"].detect_trend()
        if trend.severity != "OK":
            signals.append(trend)
        return HealthStatus(signals)

    def post_generation_check(self, text: str) -> HealthStatus:
        """Проверка ПОСЛЕ генерации: все каналы."""
        signals = []
        signals.append(self.channels["golden"].compare(text))
        signals.append(self.channels["physics"].validate(text))
        signals.append(self.channels["observer"].evaluate(text))
        return HealthStatus(signals)

    def record_metrics(self, metrics: Dict[str, float]) -> None:
        self.channels["trend"].record(metrics)
        self.channels["history"].get("metrics", []).append(metrics)

    def can_generate(self) -> bool:
        return self.pre_generation_check().can_generate

    def apply_veto(self, status: HealthStatus) -> Optional[Dict[str, Any]]:
        """Право вето: если BLOCK/EMERGENCY — откат/реанимация."""
        if status.severity in ("BLOCK", "EMERGENCY"):
            if self.reanimation:
                return self.reanimation.execute()
            return {"veto": True, "severity": status.severity}
        return None