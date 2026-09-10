# -*- coding: utf-8 -*-
"""Персистентная память сессий для writer-core гибрида (модуль m_session_memory).

Проблема, которую решает: сессии агентов не сохраняют выводов между запусками —
каждый раз приходится заново диагностировать (md-чанки, порог gemma, какие графы
строятся). Цель: следующий запуск (новый агент/сессия) читает, что уже проверено,
какие графы эталонно строятся, какой порог gemma, какие известные баги/ловушки.

Файл: JSON (MEMORY_PATH), схема writer_core.session_memory.v1::

    {
      "schema": "writer_core.session_memory.v1",
      "updated_at": "<ISO-8601>",
      "entries": {"<дата>:<секция>": <значение>, ...},   # append-only история
      "defaults": {"gemma_threshold": 0.4, "etalon_docx": ..., "registry": ..., "golden": ...},
      "<секция>": <актуальное значение>                    # зеркало add_entry
    }

Поведение:
- load(path)  — dict; если файла нет — дефолтная структура (копия, не общий мутабельный объект).
- save(mem)   — атомарная запись JSON (utf-8, ensure_ascii=False), обновляет updated_at.
- add_entry(key, value) — дозапись в entries под ключом "<дата>:<секция>" (ключ
  фиксирован контрактом: повторный add_entry той же секции в тот же день —
  upsert, обновляет запись дня; история секции хранится по дням), зеркалит
  значение в mem[<key>] и сохраняет файл.
  value: dict (контракт) или любой JSON-серизуемый объект (list для known_pitfalls).
- get(секция) — последняя запись секции (dict/list) или None. Приоритет: точный ключ
  в entries -> последняя по дате запись с суффиксом ":<секция>" -> зеркало верхнего уровня.

Модуль автономный: только stdlib (copy, datetime, json, os). Существующие модули
харнесса не импортируются и не модифицируются.
"""
from __future__ import annotations

import copy
import datetime
import json
import os

MEMORY_PATH = os.path.join(os.environ.get("WRITER_RUNS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")), "session_memory.json")
SCHEMA = "writer_core.session_memory.v1"

DEFAULT_MEMORY: dict = {
    "schema": SCHEMA,
    "updated_at": None,
    "entries": {},
    "defaults": {
        "gemma_threshold": 0.4,
        "etalon_docx": os.environ.get("WRITER_ETALON_DOCX"),
        "registry": os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph_registry.yaml"),
        "golden": os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "fixtures", "linguistics", "golden_traps.yaml"),
    },
}


def _now_iso() -> str:
    """ISO-8601 метка времени с точностью до секунды."""
    return datetime.datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    """Дата для ключа записи: YYYY-MM-DD."""
    return datetime.date.today().isoformat()


def _entry_key(section: str) -> str:
    """Ключ записи в entries: '<дата>:<секция>'."""
    return f"{_today()}:{section}"


def default_memory() -> dict:
    """Свежая дефолтная структура (глубокая копия — вызывающий может мутировать)."""
    return copy.deepcopy(DEFAULT_MEMORY)


def load(path: str = MEMORY_PATH) -> dict:
    """Вернуть память как dict. Если файла нет — вернуть дефолтную структуру.

    Fail-closed: битый JSON и другие ошибки чтения пробрасываются (лучше упасть
    явно, чем молча пересоздать память и потерять историю).
    """
    if not os.path.exists(path):
        return default_memory()
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(mem: dict, path: str = MEMORY_PATH) -> dict:
    """Записать память в JSON (utf-8, ensure_ascii=False) и обновить updated_at.

    Возвращает mem для удобства цепочек вызовов.
    """
    mem["updated_at"] = _now_iso()
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(mem, fh, ensure_ascii=False, indent=2)
    return mem


def add_entry(key: str, value, path: str = MEMORY_PATH) -> dict:
    """Дозапись в mem['entries'] под ключом '<дата>:<секция>' + сохранение.

    - key    — секция (например, 'etalon_graph_stats', 'known_pitfalls').
    - value  — dict (контракт) или любой JSON-серизуемый объект (список для
      known_pitfalls). Тип не ограничиваем жёстко: список — валидные данные.
    - Ключ записи = '<дата>:<секция>' (контракт). Повторный add_entry той же
      секции в тот же день — upsert (обновляет запись дня); история секции
      накапливается по дням. get() всегда отдаёт последнее значение.
    - Зеркало: актуальное значение кладётся и в mem[<key>], чтобы потребитель
      читал напрямую: load()['known_pitfalls'].
    Возвращает обновлённую память.
    """
    mem = load(path)
    mem["entries"][_entry_key(key)] = value
    mem[key] = value
    save(mem, path)
    return mem


def get(key_section: str, mem: dict | None = None, path: str = MEMORY_PATH):
    """Вернуть последнюю запись секции (dict/list) или None.

    Приоритет поиска:
    1. точный ключ в entries (если передан полный датированный ключ);
    2. последняя по дате запись с суффиксом ':<key_section>' (ISO-даты в префиксе
       сортируются лексикографически, поэтому 'последняя' = max по ключу);
    3. зеркало верхнего уровня mem[key_section].
    """
    if mem is None:
        mem = load(path)
    entries = mem.get("entries") or {}
    if key_section in entries:
        return entries[key_section]
    matches = [(k, v) for k, v in entries.items() if k.endswith(":" + key_section)]
    if matches:
        return sorted(matches, key=lambda kv: kv[0])[-1][1]
    if key_section in mem:
        return mem[key_section]
    return None


if __name__ == "__main__":  # краткая самопроверка / справка для агента
    mem = load()
    print("schema:", mem.get("schema"))
    print("defaults:", json.dumps(mem.get("defaults", {}), ensure_ascii=False))
    sections = [k for k in mem if k not in ("schema", "updated_at", "entries", "defaults")]
    print("sections:", sections)
