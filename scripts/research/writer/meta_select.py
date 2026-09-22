#!/usr/bin/env python3
"""Мета-выбор писателя: оверлеп маркеров (0₽) → fallback LLM-дебаты (~0.02₽).

Выбирает лучшего писателя-генератора для патча по:
1. Детерминированный оверлеп: keywords узла ∩ markers роли
2. При неоднозначности — meta-select через LLM (дешёвый deepseek-v4-flash)
"""

import json
import yaml
from pathlib import Path
from typing import Optional

from config_loader import get

from sexpr import SExpr, format_sexpr, parse, has_marker, and_pred, or_pred, not_pred


def load_registry(path: str = None) -> dict:
    if path is None:
        path = str(Path(__file__).resolve().parent / "writer_registry.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def _norm(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", s.lower().strip())


def _overlap_score(keywords: list[str], markers: list[str]) -> int:
    score = 0
    for kw in keywords:
        kw_n = _norm(kw)
        for m in markers:
            if _norm(m) in kw_n or kw_n in _norm(m):
                score += 1
    return score


def select_writer_deterministic(
    keywords: list[str],
    registry: dict,
    min_score: int = None,
) -> list[dict]:
    if min_score is None:
        min_score = get("meta_select.min_score", 1)
    candidates = []
    for writer in registry.get("domain_writers", {}).values():
        score = _overlap_score(keywords, writer.get("markers", []))
        if score >= min_score:
            candidates.append({
                "id": writer["id"],
                "description": writer["description"],
                "domain": writer.get("domain", ""),
                "score": score,
                "model": writer.get("model", "deepseek-v4-flash"),
                "context_vector": writer.get("context_vector", "physical"),
            })
    candidates.sort(key=lambda c: -c["score"])
    return candidates


def select_writer(
    keywords: list[str],
    registry: dict = None,
    force_llm: bool = False,
) -> dict:
    if registry is None:
        registry = load_registry()

    candidates = select_writer_deterministic(keywords, registry)

    if not candidates:
        return {
            "method": "fallback",
            "writer": {
                "id": "writer-generator",
                "description": "Универсальный писатель-генератор (fallback)",
                "model": "deepseek-v4-flash",
                "context_vector": "physical",
            },
            "candidates": [],
        }

    if len(candidates) == 1 and not force_llm:
        return {
            "method": "overlap",
            "writer": candidates[0],
            "candidates": candidates,
        }

    ambiguous = len(candidates) > 1 or force_llm
    if ambiguous:
        picked = _llm_select(keywords, candidates)
        if picked is not None:
            return picked

    return {
        "method": "overlap",
        "writer": candidates[0],
        "candidates": candidates,
        "meta_select_prompt": _meta_select_prompt(keywords, candidates) if ambiguous else None,
    }


def _meta_select_system() -> str:
    return (
        "Ты — селектор доменного писателя-генератора. "
        "По ключевым словам патча и описаниям кандидатов выбери ОДНОГО лучшего.\n"
        "Ответь строго S-expression:\n"
        "(select (writer . \"<id>\") (reason . \"<почему>\"))\n"
        "id — ровно один из id кандидатов."
    )


def _llm_select(keywords: list[str], candidates: list[dict]) -> Optional[dict]:
    """LLM-выбор при неоднозначности. None → детерминированный fallback."""
    if not get("meta_select.use_llm_when_ambiguous", True):
        return None
    try:
        from llm_client import llm_call
        prompt = _meta_select_prompt(keywords, candidates)
        text = llm_call(system=_meta_select_system(), user=prompt, role="meta_select")
    except Exception as e:  # noqa: BLE001
        return None

    picked_id = _parse_meta_select(text, candidates)
    if picked_id is None:
        return None
    picked = next((c for c in candidates if c["id"] == picked_id), None)
    if picked is None:
        return None
    return {
        "method": "meta_select",
        "writer": picked,
        "candidates": candidates,
        "meta_select_prompt": prompt,
        "meta_select_response": text,
    }


def _parse_meta_select(text: str, candidates: list[dict]) -> Optional[str]:
    """S-expression (select (writer . "id") (reason . "...")) → id кандидата."""
    try:
        sexpr = parse(text)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(sexpr, list):
        sexpr = sexpr[0] if sexpr else None
    if not isinstance(sexpr, SExpr) or sexpr.head != "select":
        return None
    ids = {c["id"] for c in candidates}
    for node in _walk_sexpr(sexpr):
        if isinstance(node, SExpr) and node.head == "writer":
            value = _dotted_value(node)
            if isinstance(value, str) and value in ids:
                return value
    return None


def _walk_sexpr(root: SExpr):
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, SExpr):
            yield node
            stack.extend(node.args)


def _dotted_value(node: SExpr):
    if len(node.args) >= 2 and node.args[0] == ".":
        return node.args[1]
    if node.args:
        return node.args[0]
    return None


def _meta_select_prompt(keywords: list[str], candidates: list[dict]) -> str:
    cand_text = "\n".join(
        f"  - {c['id']}: {c['description']} (domain: {c['domain']}, score: {c['score']})"
        for c in candidates[:3]
    )
    return f"""Выбери лучшего писателя-генератора для патча.

Ключевые слова патча: {', '.join(keywords[:10])}

Кандидаты (по оверлепу маркеров):
{cand_text}

Выбери ОДНОГО. Ответь S-expression:
(select (writer . "<id>") (reason . "<почему>"))
"""


def competence_boundaries(writer_id: str, registry: dict = None) -> SExpr:
    if registry is None:
        registry = load_registry()

    for section in [registry.get("domain_writers", {}), registry.get("meta_roles", {})]:
        for key, w in section.items():
            if w.get("id") == writer_id:
                markers = w.get("markers", [])
                domain = w.get("domain", "")

                allowed = or_pred(*[has_marker(m) for m in markers[:5]])
                forbidden = not_pred(has_marker("organic"))

                return SExpr("competence",
                    SExpr("writer", ".", writer_id),
                    SExpr("domain", ".", domain),
                    SExpr("allowed", allowed),
                    SExpr("forbidden", forbidden),
                    SExpr("context-vector", ".", w.get("context_vector", "physical")),
                )

    return SExpr("competence",
        SExpr("writer", ".", writer_id),
        SExpr("domain", ".", "universal"),
        SExpr("allowed", SExpr("any")),
        SExpr("forbidden", SExpr("none")),
    )


def check_competence(keywords: list[str], boundaries: SExpr) -> bool:
    allowed = boundaries.get("allowed")
    forbidden = boundaries.get("forbidden")

    if forbidden and forbidden.head == "not":
        inner = forbidden.args[0] if forbidden.args else None
        if inner and inner.head == "has-marker?":
            marker = inner.args[0] if inner.args else ""
            if any(_norm(marker) in _norm(kw) for kw in keywords):
                return False

    if allowed and allowed.head == "or":
        for pred in allowed.args:
            if isinstance(pred, SExpr) and pred.head == "has-marker?":
                marker = pred.args[0] if pred.args else ""
                if any(_norm(marker) in _norm(kw) for kw in keywords):
                    return True

    return True


if __name__ == "__main__":
    registry = load_registry()

    kw_physics = ["рентген", "дифракция", "нитрид", "фаза", "параметр решетки"]
    result = select_writer(kw_physics, registry)
    print(f"physics keywords: {result['method']} → {result['writer']['id']}")
    for c in result.get("candidates", [])[:3]:
        print(f"  {c['id']}: score={c['score']}")

    kw_tribo = ["износ", "трение", "твёрдость", "контактная выносливость"]
    result2 = select_writer(kw_tribo, registry)
    print(f"tribo keywords: {result2['method']} → {result2['writer']['id']}")

    kw_method = ["метод", "погрешность", "измерение", "калибровка"]
    result3 = select_writer(kw_method, registry)
    print(f"method keywords: {result3['method']} → {result3['writer']['id']}")

    boundaries = competence_boundaries("writer-physicist", registry)
    print(f"\ncompetence boundaries:\n{format_sexpr(boundaries)}")

    ok = check_competence(["рентген", "дифракция"], boundaries)
    print(f"check_competence(xrd): {ok}")

    ok2 = check_competence(["органическая химия"], boundaries)
    print(f"check_competence(organic): {ok2}")
