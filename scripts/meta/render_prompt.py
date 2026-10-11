# -*- coding: utf-8 -*-
"""
render_prompt.py — CLI: рендер промпта оркестратора с динамическими переменными.

Использование:
  python render_prompt.py <template_id> --task "..." --context "..." [--expected "..."]

Переменные из state (V-1 health, legacy, цикл) подтягиваются автоматически.
Выход: JSON {system, user, variables}.
"""
import json
import os
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent))

from prompt_engine import PromptEngine

DEFAULT_REGISTRY = Path(__file__).parent / 'templates' / 'orchestrator_templates.json'


def main() -> int:
    ap = argparse.ArgumentParser(description='Рендер промпта оркестратора')
    ap.add_argument('template_id')
    ap.add_argument('--task', default='')
    ap.add_argument('--context', default='')
    ap.add_argument('--expected', default='')
    ap.add_argument('--role', default='research-orchestrator')
    ap.add_argument('--orchestrator', default='research')
    ap.add_argument('--registry', default=str(DEFAULT_REGISTRY))
    ap.add_argument('--state-dir', default=None)
    args = ap.parse_args()

    pe = PromptEngine(args.orchestrator, state_dir=args.state_dir)
    if os.path.exists(args.registry):
        pe.load_registry(args.registry)

    overrides = {
        'role': args.role,
        'task': args.task,
        'context': args.context,
        'expected_output': args.expected,
    }
    try:
        rendered = pe.render(args.template_id, overrides=overrides)
    except KeyError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2

    out = {
        'system': rendered['system'],
        'user': rendered['user'],
        'variables': {
            'health': pe.meta.status()['health'],
            'cycle': pe.meta.status()['cycle'],
            'veto': pe.meta.status()['veto'],
            'dashboard': pe.meta.dashboard(),
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())