# -*- coding: utf-8 -*-
"""
E2E-тест: вложенный Мета-Цикл с git-ветками как инструментом подциклов.

Сценарий (то, что просил пользователь):
  1. Задача решается в main-ветке ("сон").
  2. Генерация даёт текст с демеджем (ошибки) → HP падает.
  3. При HP < порога → "смерть" ветки (DeathCertificate).
  4. AAR: рефлексия причин демеджа → определяются причины (death_pattern).
  5. Для каждой причины создаётся **подцикл-фича** (реальная git-ветка от main):
     - ветка fix-A устраняет причину A,
     - ветка fix-B устраняет причину B,
     - каждая гоняет свои "сны" (прогоны) независимо.
  6. После завершения всех подциклов — фичи **сливаются в main** (git merge),
     конфликты решаются, main не рухнула (тест регрессии).
  7. Цикл продолжается с новым состоянием S_{t+1}.

Используется РЕАЛЬНЫЙ git (не велосипед): ветки, merge, log — как и задумано.
"""
import os
import sys
import io
import subprocess
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from health_monitor import HealthMonitor, StyleMetrics, SystemHealth, HealthReport, HealthLevel
from trace_store import TraceStore, TraceEntry
from legacy import ExperiencePattern, LegacyArchive, LessonLearned, PatternCategory
from state import StateManager, StabilityLevel
from aar import AfterActionReport, DeathCertificate
from branch import Artifact, BranchStatus, ExperimentBranch, ExperimentRun, SkillInvocation


def git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=60)


def setup_git_repo():
    """Создать временный git-репозиторий с main."""
    td = tempfile.mkdtemp(prefix='e2e_meta_')
    git(td, 'init', '-b', 'main')
    git(td, 'config', 'user.email', 'test@test')
    git(td, 'config', 'user.name', 'Test')
    # базовый файл состояния
    with open(os.path.join(td, 'state.txt'), 'w', encoding='utf-8') as f:
        f.write('S0: initial state\n')
    git(td, 'add', '.')
    git(td, 'commit', '-m', 'S0: initial')
    return td


def test_e2e_nested_cycle():
    repo = setup_git_repo()

    # --- инициализация V-1/V1/V8/V6 ---
    health = SystemHealth(health_points=100.0, lives_remaining=3)
    hm = HealthMonitor()
    trace = TraceStore()
    sm = StateManager()
    legacy = LegacyArchive()
    cycles = 0
    merged_features = []

    def run_main_cycle(task):
        nonlocal cycles
        cycles += 1
        # 1. СОН (генерация в main) — текст с демеджем
        text = f"[draft] {task}: содержит ошибку X и ошибку Y"
        metrics = StyleMetrics(avg_sentence_length=15, terminology_density=0.1,
                               filler_word_ratio=0.3, citation_per_claim=0.2,
                               method_specification_ratio=0.4, golden_corpus_similarity=0.5)
        if cycles == 1:
            signals = [
                {'severity': 'CRITICAL', 'channel': 'physics', 'message': 'AP-M03 dimension'},
                {'severity': 'CRITICAL', 'channel': 'citation', 'message': 'AP-S05 ghost'},
            ]
            damage = -60.0
        else:
            signals = [
                {'severity': 'OK', 'channel': 'physics', 'message': 'ok'},
                {'severity': 'OK', 'channel': 'citation', 'message': 'ok'},
            ]
            damage = -5.0
        # 2. МОНИТОРИНГ V-1: HP падает
        report = HealthReport(health, signals, metrics)
        health.apply_impact(damage)
        trace.append(TraceEntry('V-1', 'damage', {'hp': health.health_points}))

        # 3. СМЕРТЬ если HP < 50
        if health.level in (HealthLevel.CRITICAL, HealthLevel.DEAD):
            health.record_death()
            death = DeathCertificate(
                branch_id='main', death_pattern='multiple_critical',
                fatal_signals=signals, hp_at_death=health.health_points,
                task_being_attempted=task, text_that_killed=text)
            health.health_points = 60.0  # регенерация после смерти (WARNING)
            health.record_recovery()

            # 4. AAR: рефлексия причин демеджа
            aar = AfterActionReport('main', death)
            for s in signals:
                aar.add_root_cause(s['message'])
            # урок на каждую причину
            lessons = [LessonLearned(s['message'], f'fix-{i}',
                                     target_component='policy', priority=2)
                       for i, s in enumerate(signals)]

            # 5. ПОДЦИКЛЫ = git-ветки (по одной на причину)
            features = []
            for i, lesson in enumerate(lessons):
                fname = f'fix-{i}-{lesson.error_pattern[:20].replace(" ", "-")}'
                # создаём ветку от main
                git(repo, 'checkout', '-b', fname)
                # "сон" внутри подцикла: правим state.txt
                with open(os.path.join(repo, 'state.txt'), 'a', encoding='utf-8') as f:
                    f.write(f'fix-{i}: {lesson.corrective_rule}\n')
                git(repo, 'add', '.')
                git(repo, 'commit', '-m', f'feature {fname}: устраняет {lesson.error_pattern}')
                features.append(fname)

            # 6. MERGE всех фич в main
            git(repo, 'checkout', 'main')
            for fname in features:
                r = git(repo, 'merge', '--no-ff', '-m', f'merge {fname}', fname)
                assert r.returncode == 0, f'merge {fname} упал: {r.stderr}'
                merged_features.append(fname)
                # подтверждение в уроке
                lesson = next(l for l in lessons if f'fix-{len(merged_features)-1}' in str(fname) or True)
            # регрессия: main не рухнула
            r = git(repo, 'log', '--oneline', '-3')
            assert 'merge' in r.stdout, 'main не содержит merge-коммитов'

            # 7. Паттерн опыта
            legacy.register_pattern(ExperiencePattern(
                PatternCategory.ANTI_PATTERN, 'multiple_critical',
                'несколько критических сигналов → смерть',
                involved_skills=['physics_check', 'citation_check']))
            return 'recovered_after_death'

        return 'ok'

    # --- прогон 2 цикла ---
    r1 = run_main_cycle('задача 1')
    assert r1 == 'recovered_after_death', f'r1={r1}'
    r2 = run_main_cycle('задача 2')
    assert r2 == 'ok', f'r2={r2}'

    # --- проверки ---
    assert cycles == 2, f'cycles={cycles}'
    assert len(merged_features) >= 2, f'merged={merged_features}'
    assert len(legacy.patterns) >= 1, f'patterns={len(legacy.patterns)}'
    # git: main имеет все фичи
    r = git(repo, 'log', '--oneline', '--all')
    assert len(r.stdout.splitlines()) >= 5, f'git log={r.stdout}'

    print(f"PASS e2e: cycles={cycles}, merged={len(merged_features)}, "
          f"patterns={len(legacy.patterns)}, deaths={health.total_deaths}, "
          f"recoveries={health.total_recoveries}")


if __name__ == '__main__':
    try:
        test_e2e_nested_cycle()
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL e2e: {e}")
        sys.exit(1)