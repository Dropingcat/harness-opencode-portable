# -*- coding: utf-8 -*-
"""Тесты PromptEngine (V5)."""
import os, sys, io, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from prompt_engine import PromptEngine, Template


def test_render_basic():
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td)
        result = pe.render('task_intro', overrides={'task': 'Проанализируй XRD',
                                                    'context': 'Р18 азотирование',
                                                    'expected_output': 'JSON'})
        assert 'Проанализируй XRD' in result['user']
        assert 'HP=' in result['system']  # переменная из health
        assert 'test-orchestrator' in result['system']


def test_render_required_missing():
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td)
        try:
            # убираем task
            pe.render('task_intro', overrides={'context': 'x'})
            assert False, 'должна быть ошибка'
        except ValueError:
            assert True


def test_custom_template():
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td)
        pe.register(Template('my', '1.0', 'custom',
                             'Sys: HP={health_hp} level={health_level}',
                             'User: {task}',
                             required_vars=['task']))
        r = pe.render('my', overrides={'task': 'T'})
        assert 'HP=' in r['system']
        assert 'T' in r['user']


def test_provider():
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td)
        pe.providers['dynamic_data'] = lambda: 'XRD=52.4deg'
        pe.register(Template('p', '1.0', 'custom', 'Sys: {dynamic_data}', 'User: {task}',
                             required_vars=['task']))
        r = pe.render('p', overrides={'task': 'T'})
        assert 'XRD=52.4deg' in r['system']


def test_registry_save_load():
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td)
        pe.register(Template('t2', '2.0', 'k', 'Sys {a}', 'User {b}', required_vars=['a', 'b']))
        reg = os.path.join(td, 'registry.json')
        pe.save_registry(reg)
        pe2 = PromptEngine('test', state_dir=td)
        pe2.load_registry(reg)
        r = pe2.render('t2', overrides={'a': 'A', 'b': 'B'})
        assert 'A' in r['system'] and 'B' in r['user']


def test_veto_in_vars():
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td, )
        pe.meta.health.health_points = 5.0
        pe.meta.health.lives_remaining = 0
        vars_ = pe._health_text(pe.meta.status())
        assert 'HP=5' in vars_
        assert pe.meta.veto() is True


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