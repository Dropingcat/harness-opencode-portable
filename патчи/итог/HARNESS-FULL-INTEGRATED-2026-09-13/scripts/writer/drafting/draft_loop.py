#!/usr/bin/env python3
"""draft_loop.py — детерминированный цикл черновиков для DOM YAML (WS-18).

Поток (модель-агностично, код решает):
  1. Декомпозиция абзаца черновика -> claims (ядро extractor, с координатами start/end).
  2. Матчинг с DOM: известные claims связываются, НОВЫЕ помечаются needs_source.
  3. Полнота параграфа: каждый фактический claim либо известен (source есть), либо
     новый (нужен запрос источника), либо параграф неполон.
  4. Стилистический синтез: граф абзаца (graph_builder) сравнивается с графами
     референс-работ из академ-источников (каждая тоже разбита на claims+graphs)
     -> рекомендации по структуре/стилю.

Режимы:
  анализ (default): читает DOM + черновик, пишет JSON-отчёт. НИЧЕГО не меняет.
  --apply: обновляет DOM — заполняет paragraph.text, добавляет новые claims
           (temp id + needs_source), пишет draft_log. БЕЗОПАСНО (append-only).

Примеры:
  python draft_loop.py --text draft_para.md --dom slug-dom.yaml
  python draft_loop.py --text draft_para.md --dom slug-dom.yaml --apply
  python draft_loop.py --text draft_para.md --dom slug-dom.yaml --ref refs/ --apply
  python draft_loop.py --text - --dom slug-dom.yaml      # stdin
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML required (pip install PyYAML)")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"DOM {path} top-level must be mapping")
    return data


def _load_text(path_or_dash: str) -> str:
    if path_or_dash == "-":
        return sys.stdin.read()
    with open(path_or_dash, "r", encoding="utf-8") as f:
        return f.read()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _same_semantic(x: str, y: str) -> bool:
    a = _norm(x).rstrip(".,;!?()")
    b = _norm(y).rstrip(".,;!?()")
    return a in b or b in a


# ------------------------- нормализация для матчинга -------------------------
# Черновик несёт markdown-разметку (**, ~~, [LEGACY], ссылки [C-xxx]/[S-xxx]),
# которой нет в текстах claims DOM. Перед сравнением сходства обе стороны
# приводим к чистому виду: убираем разметку, ссылки, стрики; нижний регистр;
# сжатие пробелов. Ссылки вырезаем и в фазе детерминированного связывания
# (pass 1), и в текстовом сходстве (pass 2), чтобы не искажали токены.

_CLAIM_REF_RE = re.compile(r"\[(C-[0-9A-Za-z._:-]+)\]")      # только claim-ссылки
_REF_TOKEN_RE = re.compile(r"\[(?:C|S|§)-[0-9A-Za-z._:-]+\]")  # любые ссылки-маркеры
_LEGACY_RE = re.compile(r"\[LEGACY\]", re.IGNORECASE)
_STRIKE_RE = re.compile(r"~~.*?~~", re.DOTALL)  # ~~...~~ = удалённый текст (убираем целиком)


def _strip_markdown(s: str) -> str:
    s = _STRIKE_RE.sub(" ", s)
    s = _REF_TOKEN_RE.sub(" ", s)
    s = _LEGACY_RE.sub(" ", s)
    s = s.replace("**", " ").replace("__", " ").replace("~~", " ")
    return re.sub(r"[`*_]", " ", s)


def _norm_for_match(s: str) -> str:
    return re.sub(r"\s+", " ", _strip_markdown(s).lower()).strip()


# ------------------------- 1. декомпозиция -------------------------

def _decompose(text: str, para_id: str) -> tuple[list[dict], dict]:
    """Декомпозиция абзаца через ядро extractor -> (claims, graphs)."""
    try:
        from scripts.writer.extractor import extract_all, build_graphs
        res = extract_all(text, para_id)
        claims = [{"text": c.get("text", ""), "span": c.get("raw_span") or c.get("text", ""),
                   "start": c.get("start"),
                   "end": c.get("end"), "kind": c.get("claim_kind", "OBSERVATIONAL")}
                  for c in res.claims]
        graphs = build_graphs(
            {"claims": [{"text": c.get("text", ""), "start": c.get("start"),
                         "end": c.get("end"), "role": "факт"} for c in res.claims],
             "objects": res.objects},
            {"connectors": [], "chreia": [], "figures": [], "morphology": {}},
            para_id,
        )
        if claims:
            return claims, {"nodes": graphs["nodes"], "edges": graphs["edges"]}
        # A non-empty paragraph with zero semantic claims is a degraded extraction,
        # not a successful empty result. Preserve explicit [C-*] markers by
        # falling back to sentence-level spans so the deterministic matcher can
        # still bind an agent draft to the DOM.
        if text.strip():
            raise ValueError("empty_claim_extraction")
        return [], {"nodes": graphs["nodes"], "edges": graphs["edges"]}
    except Exception:
        # fallback: предложения без ядра
        parts = [p.strip() for p in re.split(
            r"(?<=\])\s+(?=(?!\[)\S)|(?<=[.;!?…])\s+(?=[А-ЯЁA-Z0-9«\"(])",
            text,
        ) if p.strip()]
        if not parts and text.strip():
            parts = [text.strip()]
        claims = [{"text": p, "span": p, "start": None, "end": None, "kind": "OBSERVATIONAL",
                   "degraded_extraction": True} for p in parts]
        # Keep graph construction deterministic even in degraded mode.
        try:
            from scripts.writer.extractor import build_graphs
            graphs = build_graphs(
                {"claims": [{"text": c["text"], "start": c.get("start"),
                              "end": c.get("end"), "role": "факт"} for c in claims],
                 "objects": []},
                {"connectors": [], "chreia": [], "figures": [], "morphology": {}},
                para_id,
            )
            return claims, {"nodes": graphs["nodes"], "edges": graphs["edges"]}
        except Exception:
            return claims, {"nodes": [], "edges": []}


# ------------------------- 2. матчинг с DOM -------------------------

def _match_to_dom(claims: list[dict], dom_claims: list[dict]) -> tuple[list[dict], list[dict]]:
    """(known, new): известные claims связаны с id в DOM, новые — кандидаты.

    Два прохода (детерминированно, без LLM):
      Pass 1 — связывание по явной ссылке [C-<id>] внутри полного span фрагмента:
               если <id> есть в DOM, связываем уверенно (match_mode='link'),
               ДО текстового сходства. Явная ссылка — детерминированный указатель
               на claim_id (зеркалит гейт citation_trace), дублей не создаёт.
      Pass 2 — текстовое сходство для фрагментов БЕЗ ссылок (или с битыми
               ссылками): пересечение нормализованных токенов (markdown/ссылки
               вырезаны), порог 0.55 НЕ меняется. Один dom-claim на один
               fuzzy-матч (fuzzy_used), поведение для новых фрагментов
               (needs_source) сохраняется.
    """
    known, new = [], []
    dom_by_id = {str(dc.get("id")): dc for dc in dom_claims
                 if isinstance(dc, dict) and dc.get("id")}
    fuzzy_used: set[str] = set()
    pending: list[dict] = []

    # Pass 1: детерминированное связывание по [C-<id>]
    for c in claims:
        span = c.get("span") or c.get("text", "")
        refs = _CLAIM_REF_RE.findall(span)
        cid = next((r for r in refs if r in dom_by_id), None)
        if cid is not None:
            known.append({**c, "dom_id": cid, "match_score": 1.0, "match_mode": "link"})
        else:
            pending.append(c)

    # Pass 2: текстовое сходство (только для фрагментов без валидной ссылки)
    for c in pending:
        text = c.get("span") or c.get("text", "")
        a = set(_norm_for_match(text).split())
        if not a:
            new.append({**c, "needs_source": True})
            continue
        best, best_score = None, 0.0
        for dc in dom_claims:
            dtext = dc.get("text", "")
            if not dtext:
                continue
            b = set(_norm_for_match(dtext).split())
            if not b:
                continue
            inter = len(a & b)
            score = inter / max(1, min(len(a), len(b)))
            if score > best_score:
                best_score, best = score, dc.get("id")
        if best and best_score >= 0.55 and best not in fuzzy_used:
            fuzzy_used.add(best)
            known.append({**c, "dom_id": best, "match_score": round(best_score, 2),
                          "match_mode": "text"})
        else:
            new.append({**c, "needs_source": True})
    return known, new


# ------------------------- 3. полнота параграфа -------------------------

def _paragraph_status(known: list[dict], new: list[dict]) -> dict:
    all_claims = known + new
    total = len(all_claims)
    traced = sum(1 for c in known)
    needs_source = sum(1 for c in new)
    incomplete = [c for c in all_claims if not c.get("text")]
    return {
        "total_claims": total,
        "traced_to_dom": traced,
        "needs_source": needs_source,
        "incomplete": len(incomplete),
        "complete": total > 0 and needs_source == 0,
    }


# ------------------------- 4. стилистический синтез -------------------------

def _load_refs(ref_dir: Path) -> list[dict]:
    refs = []
    if not ref_dir.is_dir():
        return refs
    for f in sorted(ref_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(d, dict) and ("claims" in d or "graphs" in d):
                refs.append({**d, "path": str(f)})
        except Exception:
            continue
    return refs


def _graph_signature(graphs: dict) -> tuple[str, ...]:
    """Return a stable ``graph:relation`` signature from any Writer graph artifact.

    ``writer graphs`` persists a nested document -> paragraph -> graph structure,
    while older fixtures exposed ``edges`` directly.  Reference selection accepts
    both shapes so real CLI artifacts can be consumed without a one-off converter.
    """
    sig: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            edges = node.get("edges")
            if isinstance(edges, list):
                for e in edges:
                    if isinstance(e, dict) and e.get("relation"):
                        sig.add(f"{e.get('graph', '?')}:{e.get('relation', '?')}")
            for key, value in node.items():
                if key != "edges":
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(graphs)
    return tuple(sorted(sig))


def _suggest_refs(para_graph: dict, refs: list[dict], limit: int = 3) -> list[dict]:
    """Подобрать референс-работы по сходству структуры графа (стиль/аргументация)."""
    if not refs:
        return []
    psig = set(_graph_signature(para_graph))
    if not psig:
        return []
    scored = []
    for r in refs:
        rsig = set(_graph_signature(r.get("graphs", {})))
        if not rsig:
            continue
        inter = len(psig & rsig)
        score = inter / max(1, len(rsig))
        if score > 0:
            scored.append({
                "ref": r.get("id") or Path(r.get("path", "?")).stem,
                "title": r.get("title", ""),
                "graph_similarity": round(score, 2),
                "shared_edges": sorted(psig & rsig)[:8],
            })
    scored.sort(key=lambda x: -x["graph_similarity"])
    return scored[:limit]


# ------------------------- apply: обновление DOM -------------------------

def _apply(dom: dict, para_id: str, text: str, known: list[dict], new: list[dict],
           dom_path: Path) -> dict:
    """Заполнить paragraph.text, добавить новые claims (needs_source), draft_log. Append-only."""
    para = _find_paragraph(dom, para_id)
    if para is None:
        raise ValueError(f"paragraph {para_id} not found in DOM structure")
    para["text"] = text
    para["claims"] = list({*para.get("claims", []), *[c["dom_id"] for c in known]})

    existing_ids = {str(c.get("id")) for c in dom.get("claims", []) if isinstance(c, dict)}
    added = 0
    for c in new:
        nid = f"C-NEW-{added + 1:03d}"
        while nid in existing_ids:
            added += 1
            nid = f"C-NEW-{added + 1:03d}"
        existing_ids.add(nid)
        dom.setdefault("claims", []).append({
            "id": nid,
            "text": c.get("text", ""),
            "kind": "factual",
            "evidence": [],
            "needs_source": True,
            "verification": {"verdict": "OPEN", "confidence": 0.0},
        })
        added += 1
        para.setdefault("claims", []).append(nid)

    # draft_log (append)
    log = dom.setdefault("draft_log", [])
    log.append({
        "id": f"DRAFT-{len(log) + 1:02d}",
        "paragraph": para_id,
        "claims_added": added,
        "claims_linked": len(known),
        "date": "",
    })
    if yaml is not None:
        with open(dom_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(dom, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return {"claims_added": added, "claims_linked": len(known), "paragraph": para_id}


def _find_paragraph(dom: dict, para_id: str) -> dict | None:
    for ch in dom.get("structure", {}).get("chapters", []):
        for s in ch.get("sections", []):
            for p in s.get("paragraphs", []):
                if p.get("id") == para_id:
                    return p
    return None


# ------------------------- main -------------------------

def main() -> int:
    # fail-closed, детерминированно: вывод всегда UTF-8 независимо от локали.
    # Черновик несёт символы вне cp1251 (₆, ⁻², ¹², °C/с), иначе print() падает
    # UnicodeEncodeError и ломает JSON-поток для вызывающего (harness).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass

    ap = argparse.ArgumentParser(prog="draft_loop", description="Цикл черновиков DOM (WS-18)")
    ap.add_argument("--text", required=True, help="путь к черновику абзаца или '-' для stdin")
    ap.add_argument("--dom", required=True, help="путь к DOM YAML")
    ap.add_argument("--paragraph-id", required=True, help="id параграфа в DOM (PAR-...)")
    ap.add_argument("--ref", default=None, help="каталог референс-работ (JSON claims+graphs)")
    ap.add_argument("--apply", action="store_true", help="обновить DOM (заполнить paragraph, добавить новые claims)")
    ap.add_argument("--json", action="store_true", help="вывод JSON")
    args = ap.parse_args()

    try:
        text = _load_text(args.text)
        dom = _load_yaml(Path(args.dom))
        dom_claims = [c for c in dom.get("claims", []) if isinstance(c, dict)]
        claims, graphs = _decompose(text, args.paragraph_id)
        known, new = _match_to_dom(claims, dom_claims)
        status = _paragraph_status(known, new)
        refs = _load_refs(Path(args.ref)) if args.ref else []
        suggestions = _suggest_refs(graphs, refs)
    except Exception as e:
        # fail-closed: битый ввод -> JSON с error + fail_closed, exit code 2
        print(json.dumps({"ok": False, "error": str(e), "fail_closed": True},
                         ensure_ascii=False))
        return 2

    result = {
        "ok": True,
        "paragraph": args.paragraph_id,
        "status": status,
        "claims_known": known,
        "claims_new": [{"text": c["text"][:120], "needs_source": True} for c in new],
        "graph": {"nodes": len(graphs.get("nodes", [])), "edges": len(graphs.get("edges", []))},
        "style_synthesis": {
            "refs_available": len(refs),
            "suggestions": suggestions,
        },
    }

    if args.apply:
        try:
            applied = _apply(dom, args.paragraph_id, text, known, new, Path(args.dom))
            result["applied"] = applied
        except Exception as e:
            result["ok"] = False
            result["error"] = str(e)
            result["fail_closed"] = True
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())