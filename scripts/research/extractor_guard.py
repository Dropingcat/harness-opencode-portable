#!/usr/bin/env python3
"""extractor_guard.py — страховка extractor (ClaimeAI), P2.

Проблема (trace): два запуска extractor провалились —
  (1) LLM-селекция >100 c без артефакта (таймаут);
  (2) pydantic ValidationError: "Invalid JSON: control character ..." на селекции
      «Герасимова, А.Г.» — LLM вернул вложенный/битый JSON в SelectionOutput.

Фикс (три атомарных приёма, всё без зависимостей от langchain/ClaimeAI):
  - sanitize_llm_json: санитизация raw control characters + распаковка двойного
    кодирования/JSON-обвязки ПЕРЕД парсингом в pydantic;
  - run_with_retry: повтор с таймаутом на попытку (asyncio.wait_for);
  - deterministic_extract: fallback, создающий claims.json в стандартной форме.

Использование:
    import extractor_guard as eg
    clean = eg.sanitize_llm_json(raw_text)
    result = eg.run_with_retry(lambda: self._extract_claims(...), max_retries=3, timeout=100)
"""
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import re
import asyncio

__all__ = [
    "sanitize_llm_json",
    "extract_json_value",
    "RetryExhausted",
    "run_with_retry",
    "deterministic_extract",
]


def _strip_markdown_fence(text):
    """Снимает ```json ... ``` / ``` ... ``` обвязку LLM."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _remove_control_chars(text):
    """Убирает ВСЕ raw control characters (<0x20), ломающие json.loads.

    Сюда входят и raw-переносы внутри строк (именно они дают
    "Invalid JSON: control character ..."). Для валидного JSON удаление
    безопасно: вне строк переносы — просто разделители-пробелы.
    """
    return "".join(ch for ch in text if ch >= " ")


def _try_loads(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_json_value(text):
    """Извлекает первый валидный JSON-объект/массив из текста LLM.

    Возвращает (obj, text) — объект и нормализованный JSON-текст, либо (None, text).
    """
    t = _strip_markdown_fence(text)

    # 1) прямой парсинг
    obj = _try_loads(t)
    if obj is not None:
        return obj, json.dumps(obj, ensure_ascii=False)

    # 2) после удаления control characters
    cleaned = _remove_control_chars(t)
    obj = _try_loads(cleaned)
    if obj is not None:
        return obj, json.dumps(obj, ensure_ascii=False)

    # 3) JSON-строка, обёрнутая в объект {"<json>"}
    obj = _try_loads(cleaned)
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, str) and _try_loads(v) is not None:
                inner = _try_loads(v)
                return inner, json.dumps(inner, ensure_ascii=False)

    # 4) двойное кодирование вида {"{...}: LLM поставил '{' внутрь ключа
    #    ({ + пробелы + " + {, затем ключи внутреннего объекта)
    m = re.match(r'^\{\s*"\{', cleaned)
    if m:
        rest = cleaned[m.end():].lstrip()
        if rest.startswith('"'):
            repaired = '{' + rest
            obj = _try_loads(repaired)
            if obj is not None:
                return obj, json.dumps(obj, ensure_ascii=False)

    return None, cleaned


def sanitize_llm_json(text):
    """Санитизирует LLM-JSON так, чтобы pydantic/langchain распарсили его.

    Возвращает нормализованный JSON-текст (compact). Если текст не JSON —
    возвращает текст без raw control characters (безопасно для строковой обработки).
    """
    if not isinstance(text, str) or not text.strip():
        return text
    obj, normalized = extract_json_value(text)
    if obj is not None:
        return normalized
    return _remove_control_chars(_strip_markdown_fence(text))


class RetryExhausted(Exception):
    """Все попытки (с учётом таймаутов) провалились."""


def run_with_retry(fn, max_retries=3, timeout=100.0):
    """Запускает асинхронный fn с таймаутом на попытку и повторами.

    Args:
        fn: callable, возвращающий awaitable (каждая попытка с нуля).
        max_retries: число попыток.
        timeout: таймаут одной попытки (сек).

    Returns:
        Результат первого успешного вызова.

    Raises:
        RetryExhausted: если все попытки упали (таймаут или исключение).
    """
    async def _attempt():
        return await asyncio.wait_for(fn(), timeout=timeout)

    async def _run():
        last = None
        for attempt in range(1, max_retries + 1):
            try:
                return await _attempt()
            except asyncio.TimeoutError:
                last = TimeoutError(f"таймаут {timeout}s на попытке {attempt}/{max_retries}")
            except Exception as exc:  # noqa: BLE001 — пробрасываем только после исчерпания
                last = exc
        raise RetryExhausted(f"все {max_retries} попытки провалились: {last}")

    return asyncio.run(_run())


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def deterministic_extract(text, metadata="", min_len=15):
    """Детерминированное извлечение тезисов (fallback, без LLM).

    Разбивает текст на предложения-тезисы; каждое достаточно длинное предложение —
    отдельный claim в стандартной форме claims.json:
        {status: "fallback_deterministic", claims: {validated: [{text, original_sentence,
         original_index}], discarded: []}, statistics: {...}, fallback_reason: ...}
    """
    validated = []
    idx = 0
    for raw in _SENTENCE_SPLIT.split(text or ""):
        sentence = " ".join(raw.split()).strip()
        if not sentence or len(sentence) < min_len:
            continue
        validated.append({
            "text": sentence,
            "original_sentence": sentence,
            "original_index": idx,
        })
        idx += 1

    return {
        "status": "fallback_deterministic",
        "claims": {"validated": validated, "discarded": []},
        "statistics": {
            "input_source": metadata or "",
            "claims_extracted": len(validated),
            "claims_validated": len(validated),
            "claims_discarded": 0,
            "validation_rate": 1.0,
        },
        "fallback_reason": "ClaimeAI недоступен/нестабилен — детерминированное извлечение",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 extractor_guard.py <raw_llm_json_text>", file=sys.stderr)
        sys.exit(2)
    print(sanitize_llm_json(sys.argv[1]))