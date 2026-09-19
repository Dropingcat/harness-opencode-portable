#!/usr/bin/env python3
"""Извлечение ответа Sci-Bot из SPA-страницы.

Sci-Bot — SPA на vanilla JS. Ответ AI встраивается в HTML в вызов
renderSharedPage("<маркдаун>"). Извлекаем и разэкранируем.

Использование:
    python extract-answer.py page.html [--out answer.md]
"""
import argparse
import re
import sys


def extract_answer(content: str) -> str:
    marker = 'renderSharedPage("'
    start = content.index(marker) + len(marker)
    end_match = re.search(r'",\s*(true|false)', content[start:])
    if not end_match:
        raise ValueError("не найден разделитель renderSharedPage")
    raw = content[start:start + end_match.start()]
    raw = raw.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t').replace('\\/', '/')
    raw = re.sub(r'\\([^nrt"\\/])', r'\1', raw)
    return raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page", help="путь к сохранённому HTML")
    ap.add_argument("--out", default=None, help="файл для ответа (по умолчанию stdout)")
    a = ap.parse_args()

    with open(a.page, encoding="utf-8") as f:
        content = f.read()
    try:
        text = extract_answer(content)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"ok: {len(text)} chars -> {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())