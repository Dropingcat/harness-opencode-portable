# -*- coding: utf-8 -*-
"""Тесты V1 state, V4 branch, V6 legacy, orchestrator."""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from state import ErrorVector, StateManager, StateVariable, StabilityLevel, SystemState
from branch import Artifact, BranchStatus, ExperimentBranch, ExperimentRun, SkillInvocation
from legacy import (ExperiencePattern, LegacyArchive, LegacyRecord, LessonLearned,
                    PatternCategory, cosine_similarity)
from orchestrator import MetaCycleOrchestrator, DreamOutcome


# --- V1 state ---
def test_state_variable_versioning():
    v = StateVariable('x', 1, StabilityLevel.POLICY)
    v.update(2)
    assert v.version == 2
    assert v.value == 2


def test_error_vector_pareto():
    a = ErrorVector(factual=0.1, logical=0.2)
    b = ErrorVector(factual=0.3, logical=0.5)
    assert a.is_better_than(b) is True   # a лучше (ниже ошибки)


def test_state_hash_immutable():
    s1 = SystemState(variables={'a': StateVariable('a', 1, StabilityLevel.POLICY)})
    s2 = SystemState(variables={'a': StateVariable('a', 1, StabilityLevel.POLICY)})
    # разные version_id, но hash от содержимого
    assert len(s1.state_hash) == 64
    assert isinstance(s1.state_hash, str)


def test_promotion_tactic_to_policy():
    sm = StateManager()
    var = sm.set_variable('t1', True, StabilityLevel.TACTIC, ttl=5)
    for _ in range(3):
        var.record_success()
    promoted = sm.promote_tactics()
    assert 't1' in promoted
    assert sm.current.variables['t1'].stability == StabilityLevel.POLICY


def test_decay_tactics():
    sm = StateManager()
    sm.set_variable('t1', True, StabilityLevel.TACTIC, ttl=2)
    sm.decay_tactics()  # ttl 2->1
    sm.decay_tactics()  # ttl 1->0 -> удалена
    assert 't1' not in sm.current.variables


def test_apply_delta_state():
    sm = StateManager()
    sm.set_variable('a', 1, StabilityLevel.POLICY)
    old_version = sm.current.version_id
    new_state = sm.apply_delta({'var.a': 5})
    assert new_state.parent_version_id == old_version
    assert new_state.variables['a'].value == 5
    # sm.current обновился
    assert sm.current.variables['a'].value == 5


# --- V4 branch ---
def test_branch_lifecycle():
    b = ExperimentBranch('S0', {'task': 'x'})
    run = ExperimentRun(b.branch_id, 'c1', 'x')
    b.add_run(run)
    b.close(BranchStatus.VALIDATED)
    assert b.status == BranchStatus.VALIDATED
    assert b.closed_at is not None
    assert len(b.runs) == 1


def test_skill_invocation():
    s = SkillInvocation('web_search', 'retriever', {'q': 'physics'})
    assert s.skill_name == 'web_search'
    assert s.success is True


def test_artifact():
    a = Artifact('text', 'content', 'B1', ['gen'])
    assert a.artifact_type == 'text'
    assert a.tags == ['gen']


# --- V6 legacy ---
def test_pattern_success_rate():
    p = ExperiencePattern(PatternCategory.FAILURE, 'p', 'desc')
    p.record_outcome(success=True)
    p.record_outcome(success=False)
    assert p.success_rate == 0.5


def test_legacy_archive_and_search():
    la = LegacyArchive()
    rec = LegacyRecord('S0', 'hyp', 'rejected')
    lesson = LessonLearned('err', 'fix', priority=2)
    pattern = ExperiencePattern(PatternCategory.ANTI_PATTERN, 'ap', 'не делать',
                                source_lesson_ids=[lesson.lesson_id])
    rec.lessons = [lesson]
    rec.failure_patterns = [pattern]
    la.archive(rec)
    assert len(la.records) == 1
    assert 'ap' in [p.title for p in la.search_patterns('ap')]
    # lessons записаны
    assert len(la.lessons) == 1


def test_garbage_collect():
    la = LegacyArchive()
    for _ in range(3):
        la.archive(LegacyRecord('S0', 'h', 'r'))
    # ставим ttl=0 и поднимаем cycles через вызовы (times_consulted=0 -> удалятся)
    for rec in la.records:
        rec.relevance_ttl = 0
        rec.cycles_since_creation = 1  # > ttl=0
    removed = la.garbage_collect()
    assert removed == 3  # все удалены (не консультировались)
    assert len(la.records) == 0


def test_cosine():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([], []) == 0.0


# --- orchestrator ---
def test_orchestrator_success():
    orch = MetaCycleOrchestrator()
    orch.initialize()
    orch.generate_fn = lambda task, b: (f"good:{task}", [])
    orch.evaluate_fn = lambda text: ({'error_score': 0.1},
                                     [{'severity': 'OK', 'channel': 'stub'}])
    result = orch.run_task('test task')
    assert 'good:' in result
    assert orch.cycle_count == 1


def test_orchestrator_failure_archives():
    orch = MetaCycleOrchestrator()
    orch.initialize()
    orch.generate_fn = lambda task, b: (f"bad:{task}", [])
    orch.evaluate_fn = lambda text: ({'error_score': 0.9},
                                     [{'severity': 'OK', 'channel': 'stub'}])
    result = orch.run_task('fail task')
    # outcome = DEGRADATION -> archive_failure
    assert len(orch.legacy.records) == 1
    assert 'bad:' in result


def test_orchestrator_death():
    orch = MetaCycleOrchestrator()
    orch.initialize()
    orch.generate_fn = lambda task, b: (f"dead:{task}", [])
    orch.evaluate_fn = lambda text: ({'error_score': 1.0},
                                     [{'severity': 'CRITICAL', 'channel': 'physics'}])
    result = orch.run_task('dead task')
    assert len(orch.legacy.records) == 1  # архив failure
    assert 'dead:' in result


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__} {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)