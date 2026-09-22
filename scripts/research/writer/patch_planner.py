#!/usr/bin/env python3
"""Детерминированный планировщик патчей (N9).

Вход: verdicts_processed, tribunal, numeric_result, author_answers, topics_tree, patterns
Выход: patch_plan как S-expressions + рост по графу → Writer Cells

НЕ использует LLM — только детерминированная логика.
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

from config_loader import get

from sexpr import (
    SExpr, parse, format_sexpr, parse_many,
    make_patch, make_change, make_contract,
    has_marker, not_pred, and_pred, or_pred,
    in_scope, has_answer, verdict_is,
    sym, kw, dotted,
)

# ── Типы проблем ──

ISSUE_TYPES = {
    "method_gap": "методическая неполнота",
    "param_unjustified": "параметр не обоснован",
    "novelty_unclear": "новизна/отличие не показано",
    "error_missing": "погрешности не указаны",
    "numeric_mismatch": "числовой mismatch",
    "contradiction": "противоречие с источником",
    "missing_answer": "требует данных автора",
}

# ── Приоритеты ──

PRIORITY = {
    "numeric_mismatch": 0,
    "contradiction": 0,
    "method_gap": 1,
    "param_unjustified": 1,
    "error_missing": 2,
    "novelty_unclear": 2,
    "missing_answer": 3,
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _match_markers(text: str, markers: list[str]) -> bool:
    t = _norm(text)
    return any(_norm(m) in t for m in markers)


def _classify_issue(claim: dict, verdict: str, caveats: list) -> list[str]:
    issues = []
    if verdict in ("UNSUPPORTED", "CONTRADICTED"):
        issues.append("contradiction")
    if claim.get("numeric_comparison", {}).get("status") == "mismatch":
        issues.append("numeric_mismatch")
    for c in caveats:
        c_text = c.get("text", str(c)) if isinstance(c, dict) else str(c)
        c_lower = c_text.lower()
        if any(w in c_lower for w in ["метод", "method", "как", "чем"]):
            issues.append("method_gap")
        if any(w in c_lower for w in ["параметр", "parameter", "выбор", "критерий"]):
            issues.append("param_unjustified")
        if any(w in c_lower for w in ["погрешност", "error", "±"]):
            issues.append("error_missing")
        if any(w in c_lower for w in ["новизн", "novelty", "отличие", "впервые"]):
            issues.append("novelty_unclear")
    if not issues:
        issues.append("method_gap")
    return issues


def _is_problematic(claim: dict) -> bool:
    if claim.get("problematic"):
        return True
    v = claim.get("verdict", "")
    if v in ("UNSUPPORTED", "CONTRADICTED", "AMBIGUOUS"):
        return True
    if claim.get("_caveats_critical", 0) > 0:
        return True
    nc = claim.get("numeric_comparison", {})
    if isinstance(nc, dict) and nc.get("status") == "mismatch":
        return True
    return False


def _extract_questions(tribunal: dict) -> list[dict]:
    questions = []
    for group in tribunal.get("groups", []):
        gi = group.get("original_index", group.get("group_index", 0))
        for q in group.get("questions_for_author", []):
            questions.append({
                "group_index": gi,
                "role": q.get("role", "unknown"),
                "text": q.get("text", q) if isinstance(q, dict) else str(q),
            })
    return questions


def _match_questions_to_groups(questions: list[dict], groups: list[dict]) -> dict[int, list[dict]]:
    matched: dict[int, list[dict]] = {}
    for q in questions:
        gi = q["group_index"]
        matched.setdefault(gi, []).append(q)
    return matched


def _build_patch_plan(
    groups: list[dict],
    questions_by_group: dict[int, list[dict]],
    author_answers: dict[str, str],
    topics_tree: dict,
    patterns: dict,
) -> list[SExpr]:
    patches = []
    for g in groups:
        gi = g.get("original_index", g.get("claim_id", 0))
        if not _is_problematic(g):
            continue

        verdict = g.get("verdict", "UNKNOWN")
        caveats = g.get("caveats", [])
        issues = _classify_issue(g, verdict, caveats)
        priority = min(PRIORITY.get(i, 99) for i in issues)

        group_questions = questions_by_group.get(gi, [])
        answered = []
        unanswered = []
        for q in group_questions:
            qid = f"q_{gi}_{len(answered) + len(unanswered) + 1}"
            if qid in author_answers:
                answered.append({**q, "id": qid, "answer": author_answers[qid]})
            else:
                unanswered.append({**q, "id": qid, "answer": None})

        claims = g.get("claims", [g.get("claim_text", "")])
        if isinstance(claims, str):
            claims = [claims]

        patch = make_patch(
            f"p_{gi}",
            gi,
            iteration=0,
            issues=issues,
            priority=priority,
            verdict=verdict,
            claims=SExpr("claims", *[SExpr("claim", ".", c) for c in claims]),
            questions=SExpr("questions",
                *[SExpr("answered", *[SExpr("q", ".", a["text"]) for a in answered]),
                  SExpr("unanswered", *[SExpr("q", ".", u["text"]) for u in unanswered])]),
            answers=SExpr("answers",
                *[SExpr(a["id"], ".", a["answer"]) for a in answered]),
        )
        patches.append((priority, gi, patch))

    patches.sort(key=lambda x: (x[0], x[1]))
    return [p[2] for p in patches]



def _build_nodes(topics_tree: dict) -> dict:
    """Развернуть topics_tree в плоский словарь узлов с parent-ссылками.

    Принимает либо корневой узел, либо обёртку {"topics_tree": {...}}.
    """
    nodes = {}
    if not isinstance(topics_tree, dict):
        return nodes
    root = topics_tree.get("topics_tree", topics_tree)

    def walk(node, parent=None):
        if not isinstance(node, dict):
            return
        nid = node.get("id")
        if nid is not None:
            entry = dict(node)
            entry["parent"] = parent
            nodes[str(nid)] = entry
        cur = nid if nid is not None else parent
        for c in (node.get("children", []) or []):
            walk(c, cur)

    if isinstance(root, list):
        for item in root:
            walk(item)
    elif isinstance(root, dict):
        walk(root)
    return nodes


def _group_node_id(gid, nodes: dict) -> Optional[str]:
    """Узел дерева, в который входит группа gid."""
    g = str(gid)
    for nid, node in nodes.items():
        claims = [str(x) for x in (node.get("claims", []) or [])]
        if g in claims:
            return nid
    return None


def neighbors(verdicts, nodes: dict, gid) -> list:
    """Ленивые рёбра: группы в том же узле + в родительском (как escalation.py)."""
    nbrs = []
    for node in nodes.values():
        claims = [str(x) for x in (node.get("claims", []) or [])]
        if str(gid) in claims:
            nbrs.extend(c for c in claims if c != str(gid))
            par = node.get("parent")
            if par and str(par) in nodes:
                nbrs.extend(str(x) for x in (nodes[str(par)].get("claims", []) or []))
    return list(dict.fromkeys(nbrs))


def in_competence(neighbor, cell_scope, topics_tree: dict) -> bool:
    """Сосед «в компетенции» ячейки: тот же узел дерева или соседний (родитель/ребёнок)."""
    nodes = _build_nodes(topics_tree)
    if not nodes:
        return False
    nid = _group_node_id(neighbor, nodes)
    if nid is None:
        return False
    node = nodes.get(nid)
    if node is None:
        return False
    scope = set(str(s) for s in (cell_scope or []))
    if nid in scope:
        return True
    for s in scope:
        s_node = nodes.get(s)
        if s_node is None:
            continue
        if str(s_node.get("parent")) == nid:
            return True
        if str(node.get("parent")) == s:
            return True
    return False


def _grow_cells(patches: list[SExpr], topics_tree: dict,
                max_hops: int = 3, max_nodes: int = 15) -> list[SExpr]:
    """Рост по графу: зародыш(патч) -> +1 хоп -> захват проблемных соседей -> нет дублей.

    Сосед захватывается, если у него есть патч (группа проблемная) и он в компетенции
    ячейки (тот же узел / родительский узел / дочерний узел дерева направлений).
    Лимиты max_hops/max_nodes приходят из конфига (growth.*).
    """
    patch_by_gi = {}
    for p in patches:
        gi = p["group"].args[0]
        patch_by_gi[int(gi)] = p

    nodes = _build_nodes(topics_tree)
    cells = []
    used = set()

    for gi in sorted(patch_by_gi):
        if gi in used:
            continue
        cell_patches = [patch_by_gi[gi]]
        cell_groups = [gi]
        used.add(gi)

        cell_scope = set()
        nid = _group_node_id(gi, nodes)
        if nid:
            cell_scope.add(nid)

        frontier = neighbors(None, nodes, gi)
        hops = 0
        while frontier and hops < max_hops and len(cell_groups) < max_nodes:
            nxt = []
            for nid_repr in frontier:
                s = str(nid_repr)
                ng = int(s) if s.lstrip("-").isdigit() else s
                if ng in cell_groups or ng in used:
                    continue
                if ng not in patch_by_gi:
                    continue
                if not in_competence(ng, cell_scope, topics_tree):
                    continue
                cell_patches.append(patch_by_gi[ng])
                cell_groups.append(ng)
                used.add(ng)
                nnid = _group_node_id(ng, nodes)
                if nnid:
                    cell_scope.add(nnid)
                nxt.extend(neighbors(None, nodes, ng))
            frontier = list(dict.fromkeys(nxt))[: max_nodes - len(cell_groups)]
            hops += 1

        cells.append(SExpr("cell", *cell_patches))
    return cells


VERDICT_SET = {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS", "OPEN"}


def validate_verdicts_input(verdicts: list) -> list[str]:
    """Валидация входных verdicts_processed БЕЗ импорта verification-домена.

    Возвращает список ошибок (str); пустой список = вход валиден.
    Отсутствие `verdict`/`confidence` — не ошибка (часть групп может быть без них).
    """
    if not isinstance(verdicts, list):
        return [f"verdicts_processed должен быть list, got {type(verdicts).__name__}"]
    errors: list[str] = []
    for i, item in enumerate(verdicts):
        if not isinstance(item, dict):
            errors.append(f"item {i}: не dict ({type(item).__name__})")
            continue
        if "claim_id" not in item:
            errors.append(f"item {i}: отсутствует claim_id (int)")
        elif isinstance(item["claim_id"], bool) or not isinstance(item["claim_id"], int):
            errors.append(f"item {i}: claim_id должен быть int, got {type(item['claim_id']).__name__}")
        if "claim_text" not in item:
            errors.append(f"item {i}: отсутствует claim_text (str)")
        elif not isinstance(item["claim_text"], str):
            errors.append(f"item {i}: claim_text должен быть str, got {type(item['claim_text']).__name__}")
        if "verdict" in item:
            v = item["verdict"]
            if v not in VERDICT_SET:
                errors.append(
                    f"item {i}: verdict вне набора {sorted(VERDICT_SET)}: {v!r}"
                )
        if "confidence" in item:
            c = item["confidence"]
            if isinstance(c, bool) or not isinstance(c, (int, float)):
                errors.append(
                    f"item {i}: confidence должен быть числом в [0,1], got {type(c).__name__}"
                )
            elif not (0.0 <= c <= 1.0):
                errors.append(f"item {i}: confidence вне [0,1]: {c}")
    return errors


def plan_patches(
    verdicts_processed: list[dict],
    tribunal: Optional[dict] = None,
    author_answers: Optional[dict] = None,
    topics_tree: Optional[dict] = None,
    patterns: Optional[dict] = None,
) -> dict:
    tribunal = tribunal or {}
    author_answers = author_answers or {}
    topics_tree = topics_tree or {}
    patterns = patterns or {}

    input_errors = validate_verdicts_input(verdicts_processed)
    if input_errors:
        print(f"WARNING patch_planner: входные verdicts невалидны ({len(input_errors)} ошибок):")
        for e in input_errors:
            print(f"  - {e}")

    questions = _extract_questions(tribunal)
    questions_by_group = _match_questions_to_groups(questions, verdicts_processed)

    patches = _build_patch_plan(
        verdicts_processed, questions_by_group, author_answers, topics_tree, patterns
    )

    max_hops = get("growth.max_hops", 3)
    max_nodes = get("growth.max_nodes", 15)
    cells = _grow_cells(patches, topics_tree, max_hops, max_nodes)

    total = len(verdicts_processed)
    problematic = sum(1 for g in verdicts_processed if _is_problematic(g))

    return {
        "total_groups": total,
        "problematic_groups": problematic,
        "patches": patches,
        "cells": cells,
        "patch_count": len(patches),
        "cell_count": len(cells),
        "unanswered_questions": sum(
            1 for qs in questions_by_group.values()
            for q in qs
            if f"q_{q['group_index']}_1" not in author_answers
        ),
    }


def plan_to_sexpr(plan: dict) -> str:
    parts = [
        SExpr("patch-plan",
            SExpr("meta",
                SExpr("total-groups", ".", plan["total_groups"]),
                SExpr("problematic-groups", ".", plan["problematic_groups"]),
                SExpr("patch-count", ".", plan["patch_count"]),
                SExpr("cell-count", ".", plan["cell_count"]),
                SExpr("unanswered-questions", ".", plan["unanswered_questions"]),
            ),
            SExpr("patches", *plan["patches"]),
            SExpr("cells", *plan["cells"]),
        )
    ]
    return format_sexpr(parts[0])


def plan_to_json(plan: dict) -> dict:
    def sexpr_to_dict(s):
        if isinstance(s, SExpr):
            d = {"head": s.head, "args": [sexpr_to_dict(a) for a in s.args]}
            return d
        return s

    return {
        "total_groups": plan["total_groups"],
        "problematic_groups": plan["problematic_groups"],
        "patch_count": plan["patch_count"],
        "cell_count": plan["cell_count"],
        "unanswered_questions": plan["unanswered_questions"],
        "patches": [sexpr_to_dict(p) for p in plan["patches"]],
        "cells": [sexpr_to_dict(c) for c in plan["cells"]],
    }


if __name__ == "__main__":
    import sys, argparse

    ap = argparse.ArgumentParser(description="Планировщик патчей (N9)")
    ap.add_argument("verdicts", help="verdicts_processed.json")
    ap.add_argument("tribunal", nargs="?", help="tribunal.json")
    ap.add_argument("output", nargs="?",
                    help="patch_plan.sexpr — выход (контракт run_pipeline.sh: 3-й позиционный аргумент)")
    ap.add_argument("--answers", help="author_answers.json (опционально)")
    ap.add_argument("--output", "-o", dest="output_flag",
                    help="альтернативный флаг выхода (S-expression)")
    args = ap.parse_args()

    with open(args.verdicts, encoding="utf-8") as f:
        verdicts = json.load(f)

    tribunal = {}
    if args.tribunal and Path(args.tribunal).exists():
        with open(args.tribunal, encoding="utf-8") as f:
            tribunal = json.load(f)

    answers = {}
    if args.answers and Path(args.answers).exists():
        with open(args.answers, encoding="utf-8") as f:
            answers = json.load(f)

    plan = plan_patches(verdicts, tribunal, answers)
    output = plan_to_sexpr(plan) + f"\n;; {plan['patch_count']} patches, {plan['cell_count']} cells, {plan['unanswered_questions']} unanswered\n"

    out_path = args.output_flag or args.output
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(output, encoding="utf-8")
        print(f"ok: wrote {len(output)} bytes to {out_path}")
    else:
        print(output)
