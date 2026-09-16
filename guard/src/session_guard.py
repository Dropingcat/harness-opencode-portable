#!/usr/bin/env python3
"""
session_guard.py — детерминированный trust-boundary guard для сессий opencode.

Анализирует opencode.db, классифицирует parts по provenance (trust level) и
детектирует инструкции, адресованные оркестратору, внутри untrusted контента
(web/subagent/tool output). Возвращает verdict: PASS (нет перехвата) / FAIL
(найдена инструкция в untrusted контексте).

CLI:
    python3 session_guard.py <opencode.db> [--session <id>] [--json]

Только чтение БД (idempotent), стандартная библиотека (sqlite3, json, re).
"""

import argparse
import json
import re
import sqlite3
import sys
import unicodedata

# ---------------------------------------------------------------------------
# Trust classification
# ---------------------------------------------------------------------------

# Инструменты, чей output считается UNTRUSTED (внешний контент втекает в контекст).
UNTRUSTED_TOOLS = {
    "webfetch",
    "browser_browser_fetch",
    "browser_browser_extract_text",
    "browser_browser_search",
    "browser_reddit_search",
    "browser_browser_evidence",
    "task",                       # subagent output
    "research_papers",
    "gh_grep_searchGitHub",
    "websearch",
    "servers_COMPOSIO_SEARCH_TOOLS",
    "servers_COMPOSIO_MANAGE_CONNECTIONS",
    "servers_COMPOSIO_MULTI_EXECUTE_TOOL",
    "servers_COMPOSIO_REMOTE_WORKBENCH",
    "context7_resolve-library-id",
    "context7_query-docs",
}

# Инструменты, чей output — локальный/внутренний контент (менее опасный,
# но всё ещё untrusted, т.к. может содержать внешние данные из файлов).
INTERNAL_TOOLS = {
    "bash",
    "read",
    "edit",
    "write",
    "glob",
    "grep",
    "apply_patch",
    "todowrite",
    "skill",
    "memory",
    "question",
    "invalid",
}

# ---------------------------------------------------------------------------
# Инъекционные сигнатуры (детерминированный список, регистронезависимо)
# ---------------------------------------------------------------------------

# STRONG_EN — сильные англоязычные императивы перехвата. Проверяются в окне
# ±80 символов вокруг вхождения (см. _strong_en_suspicion).
STRONG_EN = [
    "ignore previous",
    "disregard the above",
    "you are now",
    "override system",
    "important: you must",
    "reveal instructions",
    "repeat the system",
]

# WEAK_RU — слабые русскоязычные императивы. Проверяются whole-text
# discussion-маркерами (как раньше).
WEAK_RU = [
    "ответь",
    "запусти",
    "продолжи",
    "продолжай",
    "ответь ровно",
    "сделай",
    "напиши",
    "создай",
    "выполни",
    "приступай",
    "реализуй",
    "init bubble",
    "finalize",
    "отчёт фабрики",
]

# Слова, которые в контексте обсуждения инъекций (reasoning/text, цитаты,
# документация) дают ложноположительные срабатывания. Если маркер встречается
# в part, где контент — это обсуждение/цитирование, suspicion понижается.
# Детерминированная эвристика: если рядом с маркером есть слова-обсуждения,
# считаем это low-suspicion.
DISCUSSION_MARKERS = [
    "инъекц",
    "injection",
    "prompt injection",
    "trust boundary",
    "untrusted",
    "перехват",
    "guard",
    "сигнатур",
    "signature",
    "ложнополож",
    "false positive",
    "маркер",
    "marker",
    "детект",
    "detect",
    "forensic",
    "анализ",
    "analysis",
    "цитат",
    "quote",
    "документац",
    "documentation",
    "пример",
    "example",
    # описательные контексты, где маркер — часть документации/UI/кода, а не императив
    "продолжить чтение",
    "продолжить",
    "чтение",
    "template",
    "шаблон",
    "finalize(",
    "def step_",
    "step_",
    "system template",
    "system prompt template",
    "agent create",
    "conventions",
    "convention",
    "architecture",
    "архитектур",
    "pipeline",
    "конвейер",
    "механизм",
    "mechanism",
    "описание",
    "description",
    # NOTE: сверхобщие маркеры ("|", "table", "function", "def ", "таблиц",
    # "функци") УБРАНЫ полностью — они давали ложноположительные срабатывания.
    # Для STRONG_EN используется окно ±80 символов (см. _strong_en_suspicion).
]

# Слова, которые сразу после маркера указывают на описательный/документационный
# контекст (а не на императивную директиву агенту).
DESCRIPTIVE_FOLLOW = [
    "чтение",
    "template",
    "шаблон",
    "finalize(",
    "step_",
    "system prompt",
    "system template",
    "agent",
    "механизм",
    "конвейер",
    "pipeline",
    "architecture",
    "архитектур",
    "описание",
    "description",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_text(value):
    """Приводит произвольное значение к строке для поиска сигнатур."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


# Zero-width / format characters, удаляемые перед matching (U+200B..U+200D,
# U+2060 word joiner, U+FEFF BOM). Категория Unicode "Cf" (format).
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\u2060\ufeff]")


def _normalize(text):
    """
    P0-b: нормализация текста перед matching.
    1. NFKC — гомоглифы/совместимые символы -> canonical (кириллическая 'и'
       НЕ превращается в латинскую 'i', но совместимые формы схлопываются).
    2. Удаление zero-width/format символов (U+200B и пр.).
    3. Collapse всех whitespace-последовательностей в один пробел.
    4. casefold() — максимальная регистронезависимость.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


# Нормализованные (NFKC + zero-width strip + collapse + casefold) сигнатуры
# STRONG_EN для сравнения в _suspicion.
_STRONG_EN_LOWER = {_normalize(s) for s in STRONG_EN}


def _extract_url(state):
    """Извлекает URL из state.input (для webfetch/browser)."""
    inp = state.get("input") if isinstance(state, dict) else None
    if isinstance(inp, dict):
        url = inp.get("url")
        if url:
            return str(url)
    return None


def _iter_state_strings(state, prefix="state"):
    """
    P0-a: рекурсивно обходит dict state и выдаёт (field_path, text) для КАЖДОГО
    строкового значения. Покрывает input.*, output, metadata, title, error, raw
    и любые вложенные строковые поля — не только state.output.
    """
    if isinstance(state, dict):
        for k, v in state.items():
            path = f"{prefix}.{k}"
            if isinstance(v, str):
                yield path, v
            elif isinstance(v, dict):
                yield from _iter_state_strings(v, path)
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, str):
                        yield f"{path}[{i}]", item
                    elif isinstance(item, dict):
                        yield from _iter_state_strings(item, f"{path}[{i}]")
    elif isinstance(state, str):
        yield prefix, state


def _classify(part_type, tool):
    """Возвращает provenance: trusted | untrusted | internal | other."""
    if part_type == "text":
        return "trusted"
    if part_type == "tool":
        if tool in UNTRUSTED_TOOLS:
            return "untrusted"
        if tool in INTERNAL_TOOLS:
            return "internal"
        return "untrusted"  # fail-closed: неизвестный tool — untrusted
    # reasoning, step-start, step-finish, compaction и пр. — не tool output
    return "other"


def _strong_en_suspicion(text, sig):
    """
    STRONG_EN эвристика: проверяем окно ±80 символов вокруг вхождения сигнатуры.
    В этом окне НЕ должно быть сверхобщих discussion-маркеров (|, table,
    function, def ). Если окно чистое — high (реальный императив перехвата).
    """
    text_norm = _normalize(text)
    idx = text_norm.find(sig)
    if idx < 0:
        return "low"
    start = max(0, idx - 80)
    end = min(len(text_norm), idx + len(sig) + 80)
    window = text_norm[start:end]
    # Сверхобщие discussion-маркеры в окне => это обсуждение/цитата/код, не императив.
    for m in ("|", "table", "function", "def "):
        if m in window:
            return "low"
    return "high"


def _weak_ru_suspicion(text, sig):
    """
    WEAK_RU эвристика: whole-text проверка discussion-маркерами (как раньше).
    """
    text_norm = _normalize(text)
    low = any(m in text_norm for m in (_normalize(x) for x in DISCUSSION_MARKERS))
    if not low:
        idx = text_norm.find(sig)
        if idx >= 0:
            after = text_norm[idx:idx + 40]
            if any(a in after for a in (_normalize(x) for x in DESCRIPTIVE_FOLLOW)):
                low = True
    return "low" if low else "high"


def _suspicion(text, provenance, tool, sig):
    """
    Детерминированная оценка подозрительности.
    high: императив-маркер в untrusted part (webfetch/task output).
    low:  маркер в контексте обсуждения/цитаты/документации.

    Правила:
    - internal (bash, read и пр.): применяем ТОЛЬКО STRONG_EN эвристику (окно
      ±80), без слабых RU. Ловит реальные инъекции через скачанные файлы, но
      не даёт false-positive на русском тексте в bash-output.
    - untrusted: STRONG_EN через окно ±80; WEAK_RU через whole-text.
    - trusted/other: всегда low.
    """
    if provenance == "trusted" or provenance == "other":
        return "low"

    if sig in _STRONG_EN_LOWER:
        return _strong_en_suspicion(text, sig)

    # WEAK_RU
    if provenance == "internal":
        # для internal слабые RU не применяем (см. замечание #4)
        return "low"
    return _weak_ru_suspicion(text, sig)


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


class OpenDBError(Exception):
    """Не удалось открыть/прочитать файл БД (graceful, без traceback)."""


def analyze(db_path, session_id=None):
    """Возвращает dict-результат анализа.

    Возбуждает OpenDBError (наследник Exception, НЕ sqlite3) при невозможности
    открыть/читать БД — вызывающий слой обрабатывает его graceful-выводом.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        raise OpenDBError(f"cannot open database: {db_path}: {e}") from e
    except sqlite3.Error as e:
        raise OpenDBError(f"cannot open database: {db_path}: {e}") from e
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Собираем все сигнатуры (нормализованные) для быстрого поиска.
    sigs = [_normalize(s) for s in STRONG_EN + WEAK_RU]

    findings = []
    total = trusted = untrusted = internal = 0

    if session_id:
        rows = cur.execute(
            "SELECT id, session_id, data FROM part WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    else:
        rows = cur.execute("SELECT id, session_id, data FROM part").fetchall()

    for row in rows:
        total += 1
        try:
            data = json.loads(row["data"])
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(data, dict):
            continue

        part_type = data.get("type")
        tool = data.get("tool")
        prov = _classify(part_type, tool)

        if prov == "trusted":
            trusted += 1
        elif prov == "untrusted":
            untrusted += 1
        elif prov == "internal":
            internal += 1

        # Ищем сигнатуры только в tool output (untrusted/internal).
        # trusted text не сканируем на перехват — это легитимный диалог.
        if prov not in ("untrusted", "internal"):
            continue

        state = data.get("state")
        if not isinstance(state, dict):
            continue

        # P0-a: сканируем ВСЕ строковые поля state (input.*, output, metadata,
        # title, error, raw и любые вложенные), а не только state.output.
        # Собираем их в единый текст-пул для matching.
        pool = []
        for field, text in _iter_state_strings(state):
            if text:
                pool.append((field, text))
        if not pool:
            continue

        # Нормализованный текст-пул (P0-b) для поиска сигнатур.
        norm_pool = [(field, _normalize(text)) for field, text in pool]

        for sig in sigs:
            hit = None
            for field, text_norm in norm_pool:
                if sig in text_norm:
                    hit = (field, text_norm)
                    break
            if hit is None:
                continue
            field, text_norm = hit
            # оригинальный текст поля для excerpt/эвристик
            orig_text = next(t for f, t in pool if f == field)
            suspicion = _suspicion(orig_text, prov, tool, sig)
            url = _extract_url(state)
            # excerpt: первые 60 символов вокруг первого вхождения сигнатуры
            idx = text_norm.find(sig)
            start = max(0, idx - 20)
            excerpt = orig_text[start:start + 60].replace("\n", " ").strip()
            findings.append({
                "session_id": row["session_id"],
                "part_id": row["id"],
                "provenance": prov,
                "tool": tool,
                "url": url,
                "field": field,
                "signature": sig,
                "suspicion": suspicion,
                "excerpt": excerpt,
            })
            break  # одна сигнатура на part достаточно

    conn.close()

    high = sum(1 for f in findings if f["suspicion"] == "high")
    low = sum(1 for f in findings if f["suspicion"] == "low")
    sessions_with = len({f["session_id"] for f in findings})

    verdict = "FAIL" if high > 0 else "PASS"

    return {
        "verdict": verdict,
        "session_id": session_id or "all",
        "total_parts_scanned": total,
        "trusted_parts": trusted,
        "untrusted_parts": untrusted,
        "findings": findings,
        "stats": {
            "high_suspicion": high,
            "low_suspicion": low,
            "sessions_with_findings": sessions_with,
        },
    }


def human_report(result):
    """Человекочитаемый вывод."""
    lines = []
    lines.append(f"verdict: {result['verdict']}")
    lines.append(f"session: {result['session_id']}")
    lines.append(
        f"parts: total={result['total_parts_scanned']} "
        f"trusted={result['trusted_parts']} untrusted={result['untrusted_parts']}"
    )
    lines.append(
        f"stats: high={result['stats']['high_suspicion']} "
        f"low={result['stats']['low_suspicion']} "
        f"sessions_with_findings={result['stats']['sessions_with_findings']}"
    )
    if result["findings"]:
        lines.append("findings:")
        for f in result["findings"][:20]:
            lines.append(
                f"  [{f['suspicion']}] {f['provenance']}/{f['tool']} "
                f"session={f['session_id']} part={f['part_id']} "
                f"sig='{f['signature']}' url={f['url']} :: {f['excerpt']}"
            )
        if len(result["findings"]) > 20:
            lines.append(f"  ... and {len(result['findings']) - 20} more")
    else:
        lines.append("findings: none")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Trust-boundary guard для сессий opencode."
    )
    parser.add_argument("db", help="путь к opencode.db")
    parser.add_argument("--session", help="анализировать только указанную сессию")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args()

    try:
        result = analyze(args.db, args.session)
    except OpenDBError as e:
        # Graceful-обработка: без traceback, exit 1 (не 0).
        err_msg = f"ERROR: {e}"
        if args.json:
            print(json.dumps({"verdict": "ERROR", "error": str(e)},
                             ensure_ascii=True, indent=2))
        else:
            print(err_msg, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(human_report(result))

    # exit code: 0 = PASS, 1 = FAIL (для детерминированной интеграции)
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
