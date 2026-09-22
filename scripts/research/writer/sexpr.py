#!/usr/bin/env python3
"""Легковесный S-expression парсер/принтер для внутриагентных взаимодействий.

Без зависимостей, ~150 строк. Поддерживает:
- атомы: символы, строки, числа, nil, #t/#f
- списки: (head arg1 arg2 ...)
- ключевые слова: :keyword
- комментарии: ; до конца строки

Использование:
    from sexpr import parse, format_sexpr, SExpr

    # Парсинг
    sexpr = parse('(contract writer (input (claim . "text")) (output patch))')
    sexpr["input"]["claim"]  # -> "text"

    # Форматирование
    format_sexpr(sexpr)  # -> "(contract writer\n  (input\n    (claim . \"text\"))\n  (output patch))"

    # Построение
    SExpr("contract", "writer",
          SExpr("input", SExpr("claim", ".", "text")),
          SExpr("output", "patch"))
"""

import re
from typing import Any, Union

# ── Типы ──

class SExpr:
    """S-expression: список с головой и аргументами."""
    __slots__ = ("head", "args")

    def __init__(self, head: str, *args: Any):
        self.head = head
        self.args = list(args)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.args[key]
        if isinstance(key, str):
            for a in self.args:
                if isinstance(a, SExpr) and a.head == key:
                    if len(a.args) >= 2 and a.args[0] == ".":
                        return a.args[1]
                    return a
            raise KeyError(key)
        raise TypeError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def __contains__(self, key):
        try:
            self[key]
            return True
        except (KeyError, IndexError):
            return False

    def __len__(self):
        return len(self.args)

    def __iter__(self):
        return iter(self.args)

    def __repr__(self):
        return format_sexpr(self)

    def __eq__(self, other):
        if not isinstance(other, SExpr):
            return False
        return self.head == other.head and self.args == other.args

    def to_list(self):
        return [self.head] + [a.to_list() if isinstance(a, SExpr) else a for a in self.args]


class SAtom:
    """Атом S-expression: символ, строка, число, nil, булево."""
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return str(self.value)

    def __eq__(self, other):
        if isinstance(other, SAtom):
            return self.value == other.value
        return self.value == other


# ── Парсер ──

_TOKEN_RE = re.compile(r"""
    ;[^\n]*                    |  # комментарий
    \(                         |  # открывающая скобка
    \)                         |  # закрывающая скобка
    "((?:[^"\\]|\\.)*)"        |  # строка
    :[^\s()";]+                |  # ключевое слово
    -?\d+\.?\d*(?:[eE][+-]?\d+)? |  # число
    [^\s()";]+                    # символ
""", re.VERBOSE)


def _tokenize(source: str):
    for m in _TOKEN_RE.finditer(source):
        token = m.group(0)
        if token.startswith(";"):
            continue
        yield token


def _parse_atom(token: str):
    if token == "nil":
        return None
    if token == "#t":
        return True
    if token == "#f":
        return False
    if token.startswith('"') and token.endswith('"'):
        inner = token[1:-1]
        inner = inner.replace('\\"', '"').replace('\\\\', '\\')
        return inner
    if token.startswith(":"):
        return token
    try:
        if "." in token or "e" in token.lower():
            return float(token)
        return int(token)
    except ValueError:
        return token


def _parse_tokens(tokens, pos=0):
    result = []
    while pos < len(tokens):
        t = tokens[pos]
        if t == "(":
            inner, pos = _parse_tokens(tokens, pos + 1)
            if inner and isinstance(inner[0], str) and not inner[0].startswith(":"):
                head = inner[0]
                args = [_convert_atom(a) for a in inner[1:]]
                result.append(SExpr(head, *args))
            else:
                result.append([_convert_atom(a) for a in inner])
        elif t == ")":
            return result, pos + 1
        else:
            result.append(_parse_atom(t))
            pos += 1
    return result, pos


def _convert_atom(a):
    if isinstance(a, SExpr):
        return a
    if isinstance(a, list):
        if a and isinstance(a[0], str) and not a[0].startswith(":"):
            return SExpr(a[0], *[_convert_atom(x) for x in a[1:]])
        return [_convert_atom(x) for x in a]
    return a


def parse(source: str):
    """Разобрать строку в S-expression."""
    tokens = list(_tokenize(source))
    result, _ = _parse_tokens(tokens)
    if len(result) == 1:
        return result[0]
    return result


def parse_many(source: str):
    """Разобрать несколько S-выражений подряд."""
    tokens = list(_tokenize(source))
    results = []
    pos = 0
    while pos < len(tokens):
        if tokens[pos] == "(":
            inner, pos = _parse_tokens(tokens, pos + 1)
            if inner and isinstance(inner[0], str) and not inner[0].startswith(":"):
                results.append(SExpr(inner[0], *[_convert_atom(a) for a in inner[1:]]))
            else:
                results.append([_convert_atom(a) for a in inner])
        else:
            results.append(_parse_atom(tokens[pos]))
            pos += 1
    return results


# ── Принтер ──

def _format_val(v, indent=0, width=80):
    if v is None:
        return "nil"
    if v is True:
        return "#t"
    if v is False:
        return "#f"
    if isinstance(v, str):
        if v.startswith(":"):
            return v
        if re.search(r'[\s()";]', v) or v == "":
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return v
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, SExpr):
        return format_sexpr(v, indent, width)
    if isinstance(v, list):
        return "(" + " ".join(_format_val(x, indent + 2, width) for x in v) + ")"
    return str(v)


def format_sexpr(sexpr, indent=0, width=80):
    """Форматировать S-expression в строку."""
    if not isinstance(sexpr, SExpr):
        return _format_val(sexpr, indent, width)

    parts = [sexpr.head]
    parts.extend(_format_val(a, indent + 2, width) for a in sexpr.args)

    oneline = "(" + " ".join(parts) + ")"
    if len(oneline) <= width - indent:
        return oneline

    pad = " " * (indent + 2)
    inner = ("\n" + pad).join(parts)
    return "(" + inner + ")"


# ── DSL-помощники ──

def sym(name: str):
    """Создать символ (атом)."""
    return name


def kw(name: str):
    """Создать ключевое слово."""
    return f":{name}"


def dotted(head: str, value):
    """Создать (head . value) — точечную пару."""
    return SExpr(head, ".", value)


def alist(*pairs):
    """Создать ассоциативный список: (alist (key1 . val1) (key2 . val2) ...)."""
    return SExpr("alist", *[SExpr(k, ".", v) for k, v in pairs])


def plist(*args):
    """Создать property-список: (plist :key1 val1 :key2 val2 ...)."""
    return SExpr("plist", *args)


# ── Предикаты для competence_boundaries ──

def has_marker(marker: str):
    """Предикат: (has-marker? "xrd")."""
    return SExpr("has-marker?", marker)


def not_pred(pred):
    """Предикат: (not (has-marker? "organic"))."""
    return SExpr("not", pred)


def and_pred(*preds):
    """Предикат: (and pred1 pred2 ...)."""
    return SExpr("and", *preds)


def or_pred(*preds):
    """Предикат: (or pred1 pred2 ...)."""
    return SExpr("or", *preds)


def in_scope(*scopes):
    """Предикат: (in-scope? "physics" "materials")."""
    return SExpr("in-scope?", *scopes)


def has_answer(question_id: str):
    """Предикат: (has-answer? "q_12_1")."""
    return SExpr("has-answer?", question_id)


def verdict_is(verdict: str):
    """Предикат: (verdict-is? "AMBIGUOUS")."""
    return SExpr("verdict-is?", verdict)


# ── Контракты ──

def make_contract(contract_type: str, **kwargs):
    """Создать S-expression контракта.

    (contract writer
      (input (claim . "...") (pattern . "...") (answers . "..."))
      (output (patch_diff . "...") (justification . "..."))
      (criteria (hard (only_own_claims) (numbers_from_answers))
                (soft (style_consistent)))
      (on_fail (retry_once) (escalate_to_human)))
    """
    parts = [contract_type]
    for k, v in kwargs.items():
        if isinstance(v, list):
            parts.append(SExpr(k, *v))
        elif isinstance(v, dict):
            items = []
            for sk, sv in v.items():
                items.append(SExpr(sk, ".", sv))
            parts.append(SExpr(k, *items))
        else:
            parts.append(SExpr(k, ".", v))
    return SExpr("contract", *parts)


# ── Patch diff ──

def make_patch(patch_id: str, group_index: int, **kwargs):
    """Создать S-expression патча.

    (patch p_12
      (group 12)
      (iteration 1)
      (issues "методическая неполнота")
      (change (old "K=1") (new "K=0.9"))
      (justification "Исправлен K в формуле Шеррера"))
    """
    parts = [patch_id, SExpr("group", group_index)]
    for k, v in kwargs.items():
        if isinstance(v, list):
            parts.append(SExpr(k, *v))
        else:
            parts.append(SExpr(k, ".", v))
    return SExpr("patch", *parts)


def make_change(old: str, new: str):
    """Создать (change (old . "...") (new . "..."))."""
    return SExpr("change", SExpr("old", ".", old), SExpr("new", ".", new))


# ── Сообщения агентов ──

def make_message(sender: str, receiver: str, msg_type: str, **kwargs):
    """Создать S-expression сообщения между агентами.

    (message (from critic) (to generator) (type attack)
      (body "Число не согласовано с источником")
      (confidence 0.85))
    """
    parts = [
        SExpr("from", sender),
        SExpr("to", receiver),
        SExpr("type", msg_type),
    ]
    for k, v in kwargs.items():
        if isinstance(v, SExpr):
            parts.append(SExpr(k, v))
        else:
            parts.append(SExpr(k, ".", v))
    return SExpr("message", *parts)


# ── Тесты ──

if __name__ == "__main__":
    # Парсинг
    s = parse('(contract writer (input (claim . "K=1")) (output patch) (criteria (hard only_own_claims)))')
    assert s.head == "contract"
    assert s["input"]["claim"] == "K=1"
    assert s["output"].args[0] == "patch"
    assert s["criteria"]["hard"].args[0] == "only_own_claims"
    print("parse: OK")

    # Форматирование
    formatted = format_sexpr(s)
    assert "contract" in formatted
    assert "writer" in formatted
    print("format: OK")

    # Предикаты
    pred = and_pred(has_marker("xrd"), not_pred(has_marker("organic")))
    assert pred.head == "and"
    assert pred[0].head == "has-marker?"
    assert pred[1].head == "not"
    print("predicates: OK")

    # Контракт
    c = make_contract("writer",
                      input={"claim": "K=1", "pattern": "xrd-scherrer"},
                      output={"patch_diff": "...", "justification": "..."},
                      criteria={"hard": [SExpr("only_own_claims"), SExpr("numbers_from_answers")]})
    assert c["input"]["claim"] == "K=1"
    assert c["criteria"]["hard"][0].head == "only_own_claims"
    print("contract: OK")

    # Патч
    p = make_patch("p_12", 12,
                   iteration=1,
                   issues=["методическая неполнота"],
                   change=make_change("K=1", "K=0.9"),
                   justification="Исправлен K в формуле Шеррера")
    assert p["group"].args[0] == 12
    assert p["change"]["old"] == "K=1"
    assert p["change"]["new"] == "K=0.9"
    print("patch: OK")

    # Сообщение
    m = make_message("critic", "generator", "attack",
                     body="Число не согласовано с источником",
                     confidence=0.85)
    assert m["from"].args[0] == "critic"
    assert m["to"].args[0] == "generator"
    assert m["type"].args[0] == "attack"
    assert m["confidence"] == 0.85
    print("message: OK")

    # parse_many
    ms = parse_many('(patch p_1 (group 1)) (patch p_2 (group 2))')
    assert len(ms) == 2
    assert ms[0].head == "patch"
    assert ms[1].head == "patch"
    print("parse_many: OK")

    # edge cases
    assert parse("nil") is None
    assert parse("#t") is True
    assert parse("#f") is False
    assert parse("42") == 42
    assert parse("3.14") == 3.14
    assert parse(":keyword") == ":keyword"
    assert parse('"hello world"') == "hello world"
    assert parse("symbol") == "symbol"
    print("atoms: OK")

    print("\n=== all tests passed ===")
