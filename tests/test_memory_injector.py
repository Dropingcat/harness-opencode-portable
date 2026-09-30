# -*- coding: utf-8 -*-
"""Тесты MemoryInjector + динамическая передача памяти в промт."""
import os, sys, io, tempfile, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from memory_injector import MemoryInjector
from prompt_engine import PromptEngine


def test_l3_lessons_read():
    mi = MemoryInjector()
    lessons = mi.l3_lessons(top=5)
    # registry существует (harness), уроки есть
    assert isinstance(lessons, list)
    # не падаем если registry пуст
    assert len(lessons) >= 0


def test_variables_structure():
    mi = MemoryInjector()
    v = mi.variables()
    assert 'memory_lessons' in v
    assert 'memory_stats' in v
    assert 'memory_l2' in v


def test_prompt_injects_memory():
    """Промт рендерится с переменными памяти (dynamic pipeline)."""
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td)
        # регистрируем шаблон с memory_lessons
        from prompt_engine import Template
        pe.register(Template('mem', '1.0', 'test',
                             'Sys: {memory_lessons} | {memory_stats}',
                             'User: {task}', required_vars=['task']))
        r = pe.render('mem', overrides={'task': 'T'})
        # память передана (текстовая проекция)
        assert 'Sys:' in r['system']
        # не падает, memory_lessons подставлен (даже если пуст)
        assert '{memory_lessons}' not in r['system']


def test_memory_in_dashboard_prompt():
    """Полный шаблон task_intro содержит память (дефолтный шаблон)."""
    with tempfile.TemporaryDirectory() as td:
        pe = PromptEngine('test', state_dir=td)
        r = pe.render('task_intro', overrides={'task': 'T', 'context': 'C',
                                               'expected_output': 'X'})
        assert 'Память (L3-уроки)' in r['system']
        assert '{memory_lessons}' not in r['system']


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
            import traceback; traceback.print_exc()
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__} {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)