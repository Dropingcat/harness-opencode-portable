# -*- coding: utf-8 -*-
"""Writer Core CLI entry point — запуск из любого cwd (контракт для агентов).

Использование (любой рабочий каталог):
    python scripts/writer-core/wc_cli.py plan --topic "..." --out structure_plan.json
    python scripts/writer-core/wc_cli.py review --draft d.md --contract c.json --dom dom.yaml ...
    python scripts/writer-core/wc_cli.py --help

Fail-closed: любой сбой на битом вводе -> JSON-ошибка + exit code 2.
"""
import os
import sys

_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or os.path.dirname(os.path.abspath(__file__))
if _WC_ROOT not in sys.path:
    sys.path.insert(0, _WC_ROOT)

from writer_core.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())