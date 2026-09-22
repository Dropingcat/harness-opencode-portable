#!/usr/bin/env python3
"""sci_bot_integration.py — Волна 3, этап 3.5.

Для групп без источников берёт промт из паттерна узла → sci_bot_client.ask()
→ пополняет sources.json (source_type: scihub_fulltext).

Режимы:
  --simulate   не тратить токены: генерирует правдоподобный ответ с DOI
               (тест парсинга и пополнения sources.json).

Usage:
  python3 sci_bot_integration.py <sources.json> <topics_tree.json> <patterns.json> <out_sources.json> [--simulate] [--limit N]
"""
import argparse
import json
import re
import subprocess
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import time
from pathlib import Path

SCI_CLIENT = (Path.home() / ".hermes/profiles/resercher/skills/sci-bot-search/sci_bot_client.py")
SCI_VENV = (Path.home() / ".hermes/hermes-agent/venv/bin/python3")
MAX_BURN = 30_000
FLOOR = 300_000
DOI_RE = re.compile(r"\b10\.\d{4,9}/\S+")


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def find_group_node(tt, gid):
    """Ищет узел, к которому привязана группа gid (в topics_tree.json)."""
    def walk(node):
        if str(gid) in node.get("claims", []):
            return node
        for c in node.get("children", []):
            r = walk(c)
            if r:
                return r
        return None
    return walk(tt.get("topics_tree", tt) if "topics_tree" in tt else tt)


def build_question(patterns, node, gid, claims):
    pat = patterns.get("patterns", {}).get(node["id"], {})
    focus = pat.get("focus_phrase", "") or pat.get("label", node["id"])
    question = pat.get("question", "")
    head = (claims[0][:220] + "…") if len(claims) > 220 else (claims[0] if claims else "")
    return (
        "Найди научные источники (из Sci-Hub/статей) по теме диссертации. "
        f"Направление: {focus}. Вопрос для проверки: {question} "
        f"Утверждение группы (первое): {head} "
        "Дай ответ с DOI и ГОСТ-цитатами, кратко."
    )


def parse_dois(text):
    """Извлекает DOI из текста ответа sci-bot."""
    return list(dict.fromkeys(DOI_RE.findall(text or "")))


def simulate_answer(question):
    """Фейковый ответ для --simulate: содержит правдоподобный DOI."""
    tag = str(int(time.time()))[-6:]
    return {
        "answer": (
            "По данному направлению найдены релевантные статьи. "
            "Отмечено соответствие экспериментальных данных литературе. "
            "Цитата: авторы сообщают о согласовании параметров решётки "
            "с известными данными по системам Fe-N-Cr. DOI: "
            f"10.1016/j.actamat.2024.{tag}"
        ),
        "tokens": 0,
        "ok": True,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources_json")
    ap.add_argument("topics_tree_json")
    ap.add_argument("patterns_json")
    ap.add_argument("out_sources_json")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="макс. групп обработать (0 = все)")
    args = ap.parse_args()

    sources = load_json(args.sources_json)
    topics = load_json(args.topics_tree_json)
    patterns = load_json(args.patterns_json)

    def group_id(g):
        return str(g.get("original_index", g.get("id")))

    target = []
    for g in sources.get("sources", {}).values():
        if not g.get("sources"):
            target.append(g)
        elif g.get("n_sources", len(g["sources"])) == 0:
            target.append(g)
    # без локальных источников по metadata
    meta_groups = sources.get("metadata", {}).get("total_groups", 0)

    if args.limit:
        target = target[:args.limit]

    filled = 0
    for g in target:
        gid = group_id(g)
        node = find_group_node(topics, gid)
        if not node:
            continue
        claims = g.get("claims", [])
        q = build_question(patterns, node, gid, claims)

        if args.simulate:
            res = simulate_answer(q)
            used_tokens = 0
        else:
            out = subprocess.run(
                [str(SCI_VENV), str(SCI_CLIENT), q,
                 "--max-burn", str(MAX_BURN), "--floor", str(FLOOR)],
                capture_output=True, text=True, timeout=600)
            last = (out.stdout or "").strip().splitlines()
            res = None
            if last:
                try:
                    res = json.loads(last[-1])
                except json.JSONDecodeError:
                    res = {"answer": "\n".join(last), "tokens": 0}
            if not res:
                print(f"  ✗ gid={gid}: нет ответа от sci-bot: {out.stderr[:200]}", file=sys.stderr)
                continue
            used_tokens = res.get("tokens", 0)

        doi_list = parse_dois(res.get("answer", ""))
        g.setdefault("sources", [])
        g["sources"].append({
            "descriptor": f"Sci-Bot полный текст (группа {gid}, узел {node['id']})",
            "id": f"SCIBOT-{gid}",
            "source_type": "scihub_fulltext",
            "doi": doi_list,
            "matched_materials": [],
            "matched_methods": [],
            "matched_phases": [],
            "relevance_score": 1,
            "content_excerpt": (res.get("answer", "") or "")[:500],
        })
        g["n_sources"] = len(g["sources"])
        filled += 1
        print(f"  + gid={gid} узел={node['id']} doi={len(doi_list)} токены={used_tokens}")

    sources.setdefault("metadata", {})["sci_bot_filled"] = filled
    save_json(args.out_sources_json, sources)
    print(f"✅ sci-bot: групп без источников {len(target)}, заполнено {filled}")
    print(f"   всего групп в metadata: {meta_groups}")


if __name__ == "__main__":
    main()
