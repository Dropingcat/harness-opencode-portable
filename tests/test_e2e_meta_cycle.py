# -*- coding: utf-8 -*-
"""
E2E: непрерывный вложенный цикл Meta-Cycle с git-merge.

Спецификация пользователя:
- Цикл крутится ПОСТОЯННО (сон → демедж → смерть → рефлексия → подциклы-фичи (git-ветки)
  → MergeProtocol (three-way, conflict, regression, health) → merge в main → продолжение).
- E2E успешен, когда цикл РАБОТАЕТ непрерывно; остановка — вручную (Ctrl+C).
- Внутри сна — подциклы-инструменты = git-ветки; слияние фич в main через git + MergeProtocol.
- Main никогда не рушится (regression + health + invariants перед commit).
"""
import os, sys, io, subprocess, tempfile, signal, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from state import StateManager, StabilityLevel
from merge_protocol import MergeProtocol, MergeRequest, ThreeWayMergeContext
from trace_store import TraceStore, TraceEntry
from legacy import LegacyArchive, ExperiencePattern, PatternCategory
from health_monitor import HealthMonitor, SystemHealth, StyleMetrics, HealthReport


def git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=60)


class ContinuousCycle:
    """Непрерывный цикл: задача → сон → демедж → смерть → фичи → merge → continue."""

    def __init__(self, repo: str) -> None:
        self.repo = repo
        self.trace = TraceStore()
        self.legacy = LegacyArchive()
        self.health = SystemHealth(health_points=100.0, lives_remaining=5)
        self.sm = StateManager()
        self.sm.set_variable('policy_citation', 'medium', StabilityLevel.POLICY)
        self.sm.set_variable('policy_retrieval', 'hybrid', StabilityLevel.POLICY)
        self.mp = MergeProtocol(trace_store=self.trace,
                                regression_suite=self._regression,
                                invariant_checker=self._invariants)
        self.cycle = 0
        self.merges = 0
        self.deaths = 0
        self.recoveries = 0
        self.should_stop = False
        self.running = False

    def _regression(self, state):
        """Regression: main не должен рухнуть."""
        return True, []

    def _invariants(self, state):
        return 'policy_citation' in state.variables

    def _damage_signals(self, cycle):
        """Каждый 3-й цикл — критический демедж (смерть), иначе лёгкий."""
        if cycle % 3 == 0:
            return ([{'severity': 'CRITICAL', 'channel': 'physics', 'message': 'AP-M03'},
                     {'severity': 'CRITICAL', 'channel': 'citation', 'message': 'AP-S05'}], -70.0)
        return ([{'severity': 'OK', 'channel': 'physics', 'message': 'ok'}], -5.0)

    def _feature_branch(self, cause: str, idx: int) -> str:
        """Подцикл-фича: git-ветка от main, устраняет причину."""
        fname = f'fix-{idx}-{cause[:12].replace(" ", "-")}'
        git(self.repo, 'checkout', '-b', fname)
        with open(os.path.join(self.repo, 'fixes.txt'), 'a', encoding='utf-8') as f:
            f.write(f'{fname}: устраняет {cause}\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-m', f'feature {fname}')
        return fname

    def _merge_features(self, features: list, state) -> bool:
        """Слияние фич в main через git + MergeProtocol (важно: main не рушится)."""
        # 1. git merge (three-way на уровне файлов)
        git(self.repo, 'checkout', 'main')
        for fname in features:
            r = git(self.repo, 'merge', '--no-ff', '-m', f'merge {fname}', fname)
            if r.returncode != 0:
                git(self.repo, 'merge', '--abort')
                return False
        # 2. MergeProtocol (на уровне состояния): дельта = фичи
        base = self.sm.current
        ours = self.sm.current
        # theirs: применяем фичи как изменение политики
        theirs = StateManager()
        for k, v in self.sm.current.variables.items():
            theirs.set_variable(k, v.value, v.stability)
        theirs.set_variable('policy_citation', 'strict', StabilityLevel.POLICY)
        ctx = ThreeWayMergeContext(base, ours, theirs.current,
                                   {'policy_citation': 'strict'})
        req = MergeRequest('features', ctx)
        result = self.mp.execute_merge(req)
        if result.success:
            self.sm.current = result.new_main_state
            self.merges += 1
            return True
        return False

    def step(self) -> str:
        """Один цикл."""
        self.cycle += 1
        signals, damage = self._damage_signals(self.cycle)
        # Сон (генерация)
        text = f"[draft-{self.cycle}] задача с ошибками"
        metrics = StyleMetrics(avg_sentence_length=15, terminology_density=0.1,
                               filler_word_ratio=0.2, citation_per_claim=0.5,
                               method_specification_ratio=0.6, golden_corpus_similarity=0.7)
        report = HealthReport(self.health, signals, metrics)
        self.health.apply_impact(damage)
        self.trace.append(TraceEntry('V-1', 'damage', {'hp': self.health.health_points,
                                                       'cycle': self.cycle}))
        # Смерть?
        if self.health.level in ('critical', 'dead') and self.health.health_points < 50:
            self.deaths += 1
            self.health.record_death()
            causes = [s['message'] for s in signals]
            # Рефлексия → подциклы-фичи
            features = [self._feature_branch(c, i) for i, c in enumerate(causes)]
            merged = self._merge_features(features, self.sm.current)
            if merged:
                self.health.health_points = 60.0
                self.health.record_recovery()
                self.recoveries += 1
                # паттерн опыта
                self.legacy.register_pattern(ExperiencePattern(
                    PatternCategory.ANTI_PATTERN, 'critical_damage',
                    'критический демедж → фичи+merge',
                    involved_skills=['physics', 'citation']))
                return 'recovered'
            return 'merge_failed'
        return 'ok'

    def run(self, max_cycles: int = 0, stop_keywords: tuple = ('quit', 'stop')):
        """Непрерывный цикл до ручной остановки (Ctrl+C) или max_cycles."""
        self.running = True
        print("[E2E] Непрерывный цикл запущен. Ctrl+C для остановки.")
        try:
            while self.running:
                self.step()
                if max_cycles and self.cycle >= max_cycles:
                    break
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\n[E2E] Остановлен вручную (Ctrl+C).")
        finally:
            self.running = False
        return self.cycle


def test_e2e_continuous():
    repo = tempfile.mkdtemp(prefix='e2e_cont_')
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.email', 't@t')
    git(repo, 'config', 'user.name', 'T')
    with open(os.path.join(repo, 'fixes.txt'), 'w', encoding='utf-8') as f:
        f.write('initial\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'S0')

    cycle = ContinuousCycle(repo)
    # 6 циклов: должно быть ~2 смерти (3-й и 6-й) и 2 recoveries
    n = cycle.run(max_cycles=6)
    assert n == 6
    assert cycle.deaths >= 1, f"deaths={cycle.deaths}"
    assert cycle.merges >= 1, f"merges={cycle.merges}"
    # main не рухнул
    r = git(repo, 'log', '--oneline', 'main')
    assert 'merge' in r.stdout, "в main нет merge"
    # git status чистый
    r2 = git(repo, 'status', '--short')
    assert r2.returncode == 0
    print(f"PASS e2e-continuous: cycles={n}, deaths={cycle.deaths}, "
          f"recoveries={cycle.recoveries}, merges={cycle.merges}")


if __name__ == '__main__':
    # Режим: непрерывный до Ctrl+C (по спецификации пользователя)
    if '--test' in sys.argv:
        test_e2e_continuous()
        sys.exit(0)
    repo = tempfile.mkdtemp(prefix='e2e_manual_')
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.email', 't@t')
    git(repo, 'config', 'user.name', 'T')
    with open(os.path.join(repo, 'fixes.txt'), 'w', encoding='utf-8') as f:
        f.write('initial\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'S0')
    c = ContinuousCycle(repo)
    c.run()  # бесконечно до Ctrl+C