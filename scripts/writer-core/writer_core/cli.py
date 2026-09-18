# -*- coding: utf-8 -*-
"""writer_core.cli — единый детерминированный CLI фабрики письма.

Команды:
  plan          (--doc | --bundle | --topic "<тема>") -> structure_plan.json
                (G1-дерево + G2-слоты + gaps) через structure_annotator-планировщик;
                --topic строит каркас БЕЗ документа: секции автореферата из
                SECTION_REGISTRY + слоты + gaps (вызов writing-orchestrator до research);
  draftcheck    --draft draft.md --contract writing_contract.json -> rtt_report.json
                (re-extraction черновика + RTT-дифф + constrained repair-дефекты);
  live-cycle    --bundle bundle.json --contract contract.json --draft draft.md
                [--repair] -> live_cycle_report.json (весь контур кодекра:
                bundle->claims->contract->draft re-extraction->RTT-diff->repair);
  extract       --doc -> artifact.json (hybrid_extract_document);
  graphs        --artifact -> graphs.json (+ --sqlite .db);
  annotate      --doc -> structure_plan.json (structure_annotator);
  consolidate   --versions-dir -> evolution_report.json/.md;
  vectorsim     --a --b -> cosine/dynamic_metrics;
  dom           --template writer-dom-dissertation.yaml --plan structure_plan.json
                [--claims claims.json] [--graphs graphs.json]
                [--source-kind KIND ...] --out dom.yaml
                (plan/claims/графы writer_core -> DOM YAML по контракту
                прослеживаемости для citation_trace.py).

Запуск:
  python -m writer_core.cli <command> ...   # из каталога hybrid/ (пакет на пути)

Детерминированно, без LLM. Fail-closed: битый ввод -> JSON-ошибка в stdout
+ exit code 2.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any

# Runtime paths: native HARNESS layout (scripts/writer-core), env-overridable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or (os.path.dirname(_HERE) if os.path.basename(_HERE) == "writer_core" else _HERE)
_HARNESS_ROOT = os.path.dirname(os.path.dirname(_WC_ROOT))
for _p in (_WC_ROOT, os.path.join(_WC_ROOT, "v2_extractor"), os.path.join(_WC_ROOT, "writer_core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read_json(path: str) -> Any:
    """JSON с допуском UTF-8 BOM (PowerShell Set-Content -Encoding UTF8 пишет BOM)."""
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _write_json(path: str, data: Any) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)


def _load_artifact(path: str) -> dict:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"artifact должен быть JSON-объектом, получен "
                         f"{type(data).__name__}")
    return data


def _mean_vector(vectors: list[list[float]], dim: int) -> list[float]:
    if not vectors:
        return [0.0] * dim
    n = len(vectors)
    return [round(sum(v[i] for v in vectors) / n, 6) for i in range(dim)]


# ---------------------------------------------------------------------------
# команды
# ---------------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> int:
    """plan: (--doc | --bundle) -> structure_plan.json (G1+G2+slots+gaps)."""
    from structure_annotator import annotate_document  # noqa: F401

    if args.doc:
        out = annotate_document(args.doc, max_paragraphs=args.max_paragraphs)
        plan: dict = {
            "schema": "writer_core.structure_plan.v1",
            "generated_by": "writer_core.cli.plan",
            "source": {"kind": "doc", "path": os.path.normpath(args.doc)},
            "sections": out.get("sections") or [],
            "plan": out.get("plan"),
            "slots": out.get("slots") or [],
            "gaps": out.get("gaps") or [],
            "satisfies": out.get("satisfies") or [],
            "section_status": out.get("section_status") or {},
            "meta": out.get("meta") or {},
        }
    elif args.bundle:
        bundle = _read_json(args.bundle)
        from writer_core.contracts import ResearchBundleLA
        rb = ResearchBundleLA.model_validate(bundle)
        from writer_core.factory_process import match_contract_claims
        # G2-план из бандла: каждый claim -> ClaimSlot (required в теле),
        # unresolved_questions -> gaps. Детерминированно, без выдумывания секций.
        draft_claims: list[dict] = []
        for c in rb.claims:
            draft_claims.append({"raw_span": c.proposition})
        matched = match_contract_claims(
            [{"claim_id": c.claim_id, "proposition": c.proposition}
             for c in rb.claims], draft_claims)
        slots = [{"id": f"CS_{m['contract']['claim_id']}", "type": "ClaimSlot",
                  "section": "body", "kind": "claim",
                  "expected": m["contract"]["claim_id"],
                  "proposition": m["contract"]["proposition"]}
                 for m in matched]
        gaps = [{"slot_id": f"GAP_{q}", "section": "body", "kind": "question",
                 "expected": q, "status": "GAP", "severity": "RESEARCH_REQUIRED",
                 "research_request": True, "note": "открытый вопрос бандла"}
                for q in rb.unresolved_questions]
        plan = {
            "schema": "writer_core.structure_plan.v1",
            "generated_by": "writer_core.cli.plan",
            "source": {"kind": "bundle", "path": os.path.normpath(args.bundle),
                       "task_contract": rb.task_contract},
            "sections": [],
            "plan": {"writing_objective": {"id": "WO_DOC",
                                           "type": "WritingObjective"},
                     "document_goal": {"id": "DG_DOC", "type": "DocumentGoal",
                                       "children": []},
                     "goals": [], "slots": slots, "edges": []},
            "slots": slots,
            "gaps": gaps,
            "satisfies": [],
            "section_status": {},
            "meta": {"claims_in_bundle": len(rb.claims),
                     "unresolved": len(rb.unresolved_questions)},
        }
    elif args.topic:
        # Каркас БЕЗ документа: тема -> секции SECTION_REGISTRY + слоты + gaps
        # (writing-orchestrator вызывает ПЕРЕД research — «дерево для заполнения»).
        from writer_core.live_cycle import plan_from_topic
        plan = plan_from_topic(args.topic)
    else:
        raise ValueError("plan: требуется --doc <path>, --bundle <path> "
                         "или --topic \"<тема>\"")

    _write_json(args.out, plan)
    n_sections = len(plan.get("sections") or [])
    print(json.dumps({
        "command": "plan", "out": os.path.normpath(args.out),
        "sections": n_sections,
        "section_types": [s.get("section_type") for s in plan.get("sections", [])],
        "slots": len(plan.get("slots") or []),
        "gaps": len(plan.get("gaps") or []),
        "errors": len((plan.get("meta") or {}).get("errors") or []),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_draftcheck(args: argparse.Namespace) -> int:
    """draftcheck: draft.md + writing_contract.json -> rtt_report.json."""
    from writer_core.factory_process import draftcheck, load_contract_claims

    with open(args.draft, "r", encoding="utf-8-sig") as fh:
        draft_text = fh.read()
    contract = _read_json(args.contract)
    claims = load_contract_claims(contract)
    if not claims:
        raise ValueError("writing_contract: пустой список claims")

    report = draftcheck(draft_text, claims)
    report["contract_path"] = os.path.normpath(args.contract)
    report["draft_path"] = os.path.normpath(args.draft)
    _write_json(args.out, report)
    print(json.dumps({
        "command": "draftcheck", "out": os.path.normpath(args.out),
        "verdict": report.get("verdict"),
        "defects": [{"defect": d["defect_type"], "claim_id": d["claim_id"],
                     "span": d.get("span"), "suggestion": d.get("suggestion")}
                    for d in report.get("defects") or []],
        "checked": len(report.get("checked") or []),
        "re_extraction_errors": len((report.get("re_extraction") or {})
                                    .get("errors") or []),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_live_cycle(args: argparse.Namespace) -> int:
    """live-cycle: весь контур кодекра bundle->contract->draft->rtt->repair."""
    from writer_core.live_cycle import run_live_cycle

    with open(args.draft, "r", encoding="utf-8-sig") as fh:
        draft_text = fh.read()
    report = run_live_cycle(args.bundle, args.contract, draft_text,
                            max_contract_claims=args.max_contract_claims,
                            repair=args.repair)
    _write_json(args.out, report)
    rtt = report.get("rtt_diff") or {}
    print(json.dumps({
        "command": "live-cycle", "out": os.path.normpath(args.out),
        "bundle_claims": (report.get("research_bundle") or {}).get("n_claims"),
        "contract_claims": (report.get("writer_contract") or {}).get("n_claims"),
        "contract_claims_used": (report.get("writer_contract") or {})
                                .get("n_claims_used"),
        "draft_claims_extracted": (report.get("draft") or {})
                                  .get("n_claims_extracted"),
        "verdict": rtt.get("verdict"),
        "n_defects": rtt.get("n_defects"),
        "defects_by_type": rtt.get("defects_by_type"),
        "repair": report.get("repair"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """extract: doc -> artifact.json (hybrid_extract_document)."""
    from hybrid_extract import hybrid_extract_document  # noqa: F401

    art = hybrid_extract_document(args.doc, max_paragraphs=args.max_paragraphs)
    _write_json(args.out, art)
    print(json.dumps({
        "command": "extract", "out": os.path.normpath(args.out),
        "paragraphs": (art.get("meta") or {}).get("count", 0),
        "errors": len((art.get("meta") or {}).get("errors") or []),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_graphs(args: argparse.Namespace) -> int:
    """graphs: artifact -> graphs.json (+ sqlite).

    СЕМАНТИКА skipped (осознанное решение, R6): итоговый graphs.json содержит
    ключ "skipped" — список записей ПО КАЖДОМУ ПАРАГРАФУ (build_paragraph_graphs
    возвращает per-paragraph skipped: графы реестра, не построенные из данного
    параграфа). При N параграфах один и тот же skipped-граф (G1, G10, ...)
    повторяется N раз — это НЕ баг, а следствие per-paragraph семантики:
    граф мог построиться в одном параграфе и быть skipped в другом. Агрегация
    по графу (count/paragraphs) — отдельная задача (вне scope).
    """
    from graph_builder_hybrid import (build_paragraph_graphs,  # noqa: F401
                                      graph_stats, to_sqlite, load_graph_registry)

    art = _load_artifact(args.artifact)
    registry = load_graph_registry()
    paras = art.get("paragraphs")
    if isinstance(paras, list):
        paragraph_list = paras
    else:
        paragraph_list = [art]

    graphs_out: dict[str, dict] = {}
    skipped: list[dict] = []
    errors: list[dict] = []
    conn = None
    if args.sqlite:
        parent = os.path.dirname(os.path.abspath(args.sqlite))
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(args.sqlite)
    try:
        for p in paragraph_list:
            pid = p.get("paragraph_id") or "?"
            try:
                g = build_paragraph_graphs(p, registry)
                graphs_out[pid] = g
                skipped.extend(g.get("skipped") or [])
                if conn is not None:
                    to_sqlite(g, conn)
            except Exception as e:
                errors.append({"paragraph_id": pid,
                               "error": f"{type(e).__name__}: {e}"})
        if conn is not None:
            conn.commit()
    finally:
        if conn is not None:
            conn.close()

    result = {"schema": "writer_core.graphs.v1",
              "generated_by": "writer_core.cli.graphs",
              "artifact": os.path.normpath(args.artifact),
              "graphs": graphs_out,
              "skipped": skipped,
              "errors": errors,
              "sqlite": os.path.normpath(args.sqlite) if args.sqlite else None}
    _write_json(args.out, result)
    print(json.dumps({
        "command": "graphs", "out": os.path.normpath(args.out),
        "paragraphs": len(paragraph_list),
        "graph_built": sum(1 for g in graphs_out.values() if g.get("built", 0)),
        "errors": len(errors),
        "sqlite": result["sqlite"],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    """annotate: doc -> structure_plan.json (structure_annotator)."""
    from structure_annotator import annotate_document  # noqa: F401

    out = annotate_document(args.doc, max_paragraphs=args.max_paragraphs)
    plan = {
        "schema": "writer_core.structure_plan.v1",
        "generated_by": "writer_core.cli.annotate",
        "source": {"kind": "doc", "path": out.get("path")},
        "sections": out.get("sections") or [],
        "plan": out.get("plan"),
        "slots": out.get("slots") or [],
        "gaps": out.get("gaps") or [],
        "satisfies": out.get("satisfies") or [],
        "section_status": out.get("section_status") or {},
        "tables": out.get("tables") or [],
        "meta": out.get("meta") or {},
    }
    _write_json(args.out, plan)
    print(json.dumps({
        "command": "annotate", "out": os.path.normpath(args.out),
        "sections": len(plan["sections"]),
        "section_types": [s.get("section_type") for s in plan["sections"]],
        "slots": len(plan["slots"]),
        "gaps": len(plan["gaps"]),
        "errors": len((plan.get("meta") or {}).get("errors") or []),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_consolidate(args: argparse.Namespace) -> int:
    """consolidate: versions dir -> evolution_report.json/.md."""
    from consolidation import (discover_versions, collect_corpus,  # noqa: F401
                               compute_evolution, version_similarity,
                               write_report, CORPUS_ERRORS, EVOLUTION_REPORT_JSON,
                               EVOLUTION_SUMMARY_MD)

    disc = discover_versions(args.versions_dir)
    files = disc.get("main") or []
    versions = collect_corpus(files, max_paragraphs=args.max_paragraphs)
    evolution = compute_evolution(versions)
    if args.out_dir:
        import consolidation as _c
        _c.CONSOLIDATION_DIR = args.out_dir
        _c.EVOLUTION_REPORT_JSON = os.path.join(args.out_dir, "evolution_report.json")
        _c.EVOLUTION_SUMMARY_MD = os.path.join(args.out_dir, "evolution_summary.md")
        os.makedirs(args.out_dir, exist_ok=True)
        write_report(evolution, versions)
        report_json, summary_md = _c.EVOLUTION_REPORT_JSON, _c.EVOLUTION_SUMMARY_MD
    else:
        write_report(evolution, versions)
        report_json, summary_md = EVOLUTION_REPORT_JSON, EVOLUTION_SUMMARY_MD

    summary = (evolution.get("summary") or {})
    sim = version_similarity(versions)
    print(json.dumps({
        "command": "consolidate", "versions_dir": os.path.normpath(args.versions_dir),
        "versions_processed": len(versions),
        "version_chain": summary.get("version_chain") or [],
        "corpus_errors": len(CORPUS_ERRORS),
        "trend": (summary.get("trend") or {}).get("claims"),
        "similarity_n": sim.get("n"),
        "report_json": os.path.normpath(report_json),
        "report_md": os.path.normpath(summary_md),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_vectorsim(args: argparse.Namespace) -> int:
    """vectorsim: --a --b -> cosine + dynamic_metrics."""
    from graph_vector import (vectorize, vector_schema,  # noqa: F401
                              cosine_similarity, dynamic_metrics)

    a = _load_artifact(args.a)
    b = _load_artifact(args.b)
    dim = len(vector_schema())

    def _vec(art: dict) -> list[float]:
        paras = art.get("paragraphs")
        if isinstance(paras, list) and paras:
            vecs = []
            for p in paras:
                try:
                    vecs.append(vectorize(p))
                except Exception:
                    continue
            return _mean_vector(vecs, dim)
        return vectorize(art)

    va, vb = _vec(a), _vec(b)
    cos = None
    if any(va) and any(vb):
        cos = round(float(cosine_similarity(va, vb)), 4)
    try:
        dm = dynamic_metrics(a, b)
    except Exception as e:
        dm = {"error": f"{type(e).__name__}: {e}"}
    result = {"schema": "writer_core.vectorsim.v1",
              "a": os.path.normpath(args.a), "b": os.path.normpath(args.b),
              "cosine": cos, "dynamic_metrics": dm}
    _write_json(args.out, result)
    print(json.dumps({
        "command": "vectorsim", "out": os.path.normpath(args.out),
        "cosine": cos,
        "dynamic_metrics": dm if isinstance(dm, dict) and "error" not in dm else None,
    }, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# dom: writer_core -> DOM YAML (контракт прослеживаемости)
# ---------------------------------------------------------------------------

def _normalize_dom_claims(data: Any) -> list[dict]:
    """claims-вход -> list[dict] {text, qa_status} для claims_to_dom.

    Принимает: list[claims] (hybrid_extract или bundle-claims с
    proposition/qa_status); dict с ключом "claims"; ResearchBundleLA.json
    ("schema" writer_core.research_bundle с claims[{proposition, qa_status}]).
    """
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("claims"), list):
        items = data["claims"]
    else:
        raise ValueError("dom: --claims должен быть list[claim] или "
                         '{"claims": [...]} / ResearchBundleLA')
    out: list[dict] = []
    for c in items:
        if not isinstance(c, dict):
            raise ValueError("dom: элемент claims должен быть объектом")
        out.append({
            "text": (c.get("text") or c.get("raw_span")
                     or c.get("proposition") or ""),
            "qa_status": c.get("qa_status") or "PROPOSED",
            "span": c.get("span"),
            "start": c.get("start"),
            "end": c.get("end"),
        })
    return out


def cmd_dom(args: argparse.Namespace) -> int:
    """dom: plan/claims/графы writer_core -> DOM YAML для citation_trace."""
    from writer_core.dom_builder import build_dom  # noqa: F401

    plan = _read_json(args.plan) if args.plan else None
    if plan is not None and not isinstance(plan, dict):
        raise ValueError("--plan: ожидался JSON-объект structure_plan")

    claims = None
    if args.claims:
        claims = _normalize_dom_claims(_read_json(args.claims))

    graphs = None
    if args.graphs:
        g = _read_json(args.graphs)
        if not isinstance(g, dict):
            raise ValueError("--graphs: ожидался JSON-объект")
        graphs = g

    source_kinds = list(args.source_kind) if args.source_kind else None

    # Qwen_yaml evidence-корпус: sources+claims+uncertainty из карточек литературы
    qwen_extra: dict | None = None
    if args.qwen_dir:
        from writer_core.dom_builder import qwen_to_dom
        import glob as _glob
        qwen_files = sorted(_glob.glob(os.path.join(args.qwen_dir, "Qwen_yaml_*.yaml")))
        if not qwen_files:
            raise ValueError(f"--qwen-dir: нет Qwen_yaml_*.yaml в {args.qwen_dir}")
        qwen_extra = qwen_to_dom(qwen_files)

    dom = build_dom(
        template_path=args.template,
        plan=plan,
        claims=claims,
        graphs=graphs,
        source_kinds=source_kinds,
        qwen_extra=qwen_extra,
        out_path=args.out,
    )

    # Q&A авторская маркировка неопределённости (override uncertainty)
    if args.qa and dom.get("claims"):
        from writer_core.dom_builder import qa_uncertainty, _write_yaml
        from writer_core.doc_com import try_extract_doc_text
        import os as _os
        qa_path = args.qa
        qa_text = None
        if _os.path.splitext(qa_path)[1].lower() == ".doc":
            qa_text = try_extract_doc_text(qa_path)
        elif _os.path.exists(qa_path):
            qa_text = open(qa_path, encoding="utf-8", errors="replace").read()
        if qa_text:
            qa_unc = qa_uncertainty(qa_text, dom.get("claims") or [])
            dom["uncertainty"] = {**(dom.get("uncertainty") or {}), **qa_unc}
            if dom.get("_validation") is not None:
                dom["_validation"]["qa_marked"] = len(qa_unc)
            _write_yaml(args.out, dom)
    validation = dom.get("_validation") or {}
    print(json.dumps({
        "command": "dom", "out": os.path.normpath(args.out),
        "product": (dom.get("product") or {}).get("id"),
        "chapters": len(dom.get("structure", {}).get("chapters", [])),
        "claims": len(dom.get("claims") or []),
        "graphs": len(dom.get("graphs") or []),
        "sources": len(dom.get("sources") or []),
        "uncertainty": len(dom.get("uncertainty") or {}),
        "validation": validation,
        "dom_valid": bool(validation.get("valid")),
    }, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# review — ветвистое ревью (L1/L2/L3) с циклами и эскалацией
# ---------------------------------------------------------------------------

def cmd_review(args: argparse.Namespace) -> int:
    """review: --draft --contract [--plan] [--dom] -> review_report.json."""
    from writer_core.review import REVIEW_CYCLE  # noqa: F401

    report = REVIEW_CYCLE(
        draft_path=args.draft,
        contract_claims=args.contract,
        plan=args.plan,
        dom=args.dom,
        max_iterations=args.max_iterations,
        max_contract_claims=args.max_contract_claims,
        out_path=args.out,
    )
    levels = report.get("issues_by_level") or {}
    print(json.dumps({
        "command": "review",
        "out": os.path.normpath(args.out),
        "final_verdict": report.get("final_verdict"),
        "iterations": report.get("iterations"),
        "stopped_reason": report.get("stopped_reason"),
        "escalation": report.get("escalation"),
        "n_issues": {
            "L1": len(levels.get("L1") or []),
            "L2": len(levels.get("L2") or []) if isinstance(levels.get("L2"), list) else 0,
            "L3": len(levels.get("L3") or []),
        },
        "rtt_defects_final": len(report.get("rtt_defects_final") or []),
        "trace_verdict": (report.get("trace_checks_final") or {}).get("verdict")
                         if isinstance(report.get("trace_checks_final"), dict) else None,
        "repaired_spans": len(report.get("repaired_spans") or []),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_uncertainty(args: argparse.Namespace) -> int:
    """uncertainty: --dom -> research debt (PROVISIONAL/tentative_only + requests)."""
    import yaml as _yaml
    path = args.dom
    if path.lower().endswith((".yaml", ".yml")):
        dom = _yaml.safe_load(open(path, encoding="utf-8")) or {}
    else:
        dom = json.load(open(path, encoding="utf-8"))
    if not isinstance(dom, dict):
        raise ValueError("--dom: ожидался объект DOM")

    from writer_core.uncertainty_bridge import report_uncertainty
    r = report_uncertainty(dom, out_path=args.out)
    print(json.dumps({
        "command": "uncertainty",
        "dom": os.path.normpath(path),
        "n_claims": len(dom.get("claims") or []),
        "n_readiness": r.get("n_readiness"),
        "research_requests": len(r.get("research_requests") or []),
        "out": os.path.normpath(args.out) if args.out else None,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    """register: контроль научного регистра (R1-R4)."""
    draft = open(args.draft, encoding="utf-8", errors="replace").read()
    dom = None
    if args.dom:
        import yaml as _yaml
        if str(args.dom).lower().endswith((".yaml", ".yml")):
            dom = _yaml.safe_load(open(args.dom, encoding="utf-8")) or {}
        else:
            dom = json.load(open(args.dom, encoding="utf-8"))

    from writer_core.register_control import register_check
    r = register_check(draft, dom=dom)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=2)
    print(json.dumps({
        "command": "register",
        "verdict": r.get("verdict"),
        "n_issues": sum(len(v) for v in r.get("issues_by_axis", {}).values()),
        "issues_by_axis": {k: len(v) for k, v in r.get("issues_by_axis", {}).items()},
        "out": os.path.normpath(args.out) if args.out else None,
    }, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="writer_core.cli",
        description="Детерминированный слой фабрики письма (plan/draftcheck/"
                    "extract/graphs/annotate/consolidate/vectorsim).")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("plan", help="структурный план будущего текста (G1+G2+gaps)")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--doc", help="путь к документу-образцу (docx/pdf/md)")
    g.add_argument("--bundle", help="путь к ResearchBundleLA.json")
    g.add_argument("--topic", help="тема: каркас секций БЕЗ документа (plan --topic "
                                   "\"<тема>\")")
    sp.add_argument("--out", default="structure_plan.json")
    sp.add_argument("--max-paragraphs", type=int, default=100)

    sp = sub.add_parser("draftcheck", help="RTT-дифф черновика против контракта")
    sp.add_argument("--draft", required=True, help="черновик .md/.txt")
    sp.add_argument("--contract", required=True, help="writing_contract.json")
    sp.add_argument("--out", default="rtt_report.json")

    sp = sub.add_parser("live-cycle", help="полный контур кодекра: "
                                           "bundle->contract->draft->rtt->repair")
    sp.add_argument("--bundle", required=True,
                    help="ResearchBundleLA.json (роль v1)")
    sp.add_argument("--contract", required=True,
                    help="writing_contract.json ИЛИ документ-эталон (роль v8, "
                         "docx/pdf/md)")
    sp.add_argument("--draft", required=True, help="черновик .md/.txt (роль v12)")
    sp.add_argument("--out", default="live_cycle_report.json")
    sp.add_argument("--repair", action="store_true",
                    help="constrained repair всех дефектов + повторный draftcheck")
    sp.add_argument("--max-contract-claims", type=int, default=40,
                    help="лимит claims контракта для RTT (по умолчанию 40, "
                         "как в run_live_cycle; None = все)")

    sp = sub.add_parser("extract", help="гибридная экстракция документа")
    sp.add_argument("--doc", required=True)
    sp.add_argument("--out", default="artifact.json")
    sp.add_argument("--max-paragraphs", type=int, default=50)

    sp = sub.add_parser("graphs", help="графы реестра из artifact.json")
    sp.add_argument("--artifact", required=True)
    sp.add_argument("--out", default="graphs.json")
    sp.add_argument("--sqlite", default=None, help="опциональный путь к .db")

    sp = sub.add_parser("annotate", help="разметка структуры документа")
    sp.add_argument("--doc", required=True)
    sp.add_argument("--out", default="structure_plan.json")
    sp.add_argument("--max-paragraphs", type=int, default=100)

    sp = sub.add_parser("consolidate", help="консолидация версий (v1..v12)")
    sp.add_argument("--versions-dir", required=True)
    sp.add_argument("--out-dir", default=None,
                    help="каталог отчёта (по умолчанию hybrid/consolidation)")
    sp.add_argument("--max-paragraphs", type=int, default=100)

    sp = sub.add_parser("vectorsim", help="cosine + dynamic_metrics двух артефактов")
    sp.add_argument("--a", required=True)
    sp.add_argument("--b", required=True)
    sp.add_argument("--out", default="vectorsim.json")

    sp = sub.add_parser("dom", help="writer_core -> DOM YAML по контракту "
                                     "прослеживаемости (для citation_trace.py)")
    sp.add_argument("--template", required=True,
                    help="путь к DOM-шаблону (writer-dom-dissertation.yaml)")
    sp.add_argument("--plan", default=None,
                    help="structure_plan.json (наш plan --topic)")
    sp.add_argument("--claims", default=None,
                    help="claims.json: list[claim] | {\"claims\": [...]} | "
                         "ResearchBundleLA.json")
    sp.add_argument("--graphs", default=None,
                    help="graphs.json (CLI graphs ИЛИ вывод build_paragraph_graphs)")
    sp.add_argument("--source-kind", action="append", default=None,
                    help="происхождение источника (повторяемый): raw_data/"
                         "эксперимент/published/автореферат/direct_method/"
                         "indirect_method/modeling/hypothesis")
    sp.add_argument("--qwen-dir", default=None,
                    help="папка с Qwen_yaml_*.yaml карточками литературы -> "
                         "evidence-корпус (sources+claims+uncertainty) в DOM")
    sp.add_argument("--qa", default=None,
                    help="путь к Q&A автореферата (.doc/.docx/.txt) для авторской "
                         "маркировки неопределённости (qa_uncertainty)")
    sp.add_argument("--out", default="dom.yaml")

    sp = sub.add_parser("review", help="ветвистое ревью: L1 (микро) + L2 (мезо) "
                                       "+ L3 (макро) с циклами и эскалацией")
    sp.add_argument("--draft", required=True, help="черновик .md/.txt (роль v12)")
    sp.add_argument("--contract", required=True,
                    help="writing_contract.json ИЛИ документ-эталон (роль v8, "
                         "docx/pdf/md) ИЛИ inline-JSON")
    sp.add_argument("--plan", default=None,
                    help="structure_plan.json (наш plan --topic) для L2-тира")
    sp.add_argument("--dom", default=None,
                    help="DOM YAML/JSON для цитатного гейта citation_trace (L3)")
    sp.add_argument("--out", default="review_report.json")
    sp.add_argument("--max-iterations", type=int, default=3,
                    help="максимум циклов ревью (по умолчанию 3)")
    sp.add_argument("--max-contract-claims", type=int, default=None,
                    help="лимит claims контракта для RTT (None = все)")

    sp = sub.add_parser("uncertainty", help="research debt: неопределённость claims "
                                            "DOM -> PROVISIONAL/tentative_only + "
                                            "research_requests (мост к researcher)")
    sp.add_argument("--dom", required=True, help="DOM YAML/JSON")
    sp.add_argument("--out", default=None, help="JSON-отчёт (опционально)")

    sp = sub.add_parser("register", help="контроль научного регистра черновика "
                                         "(R1 референс/R2 вектор/R3 лексика/R4 тропы). "
                                         "Канон данных vs канон знаний.")
    sp.add_argument("--draft", required=True, help="черновик .md/.txt")
    sp.add_argument("--dom", default=None, help="DOM YAML/JSON (для R1 референс-подхвата)")
    sp.add_argument("--out", default=None, help="JSON-отчёт (опционально)")
    return p


_HANDLERS = {
    "plan": cmd_plan,
    "draftcheck": cmd_draftcheck,
    "live-cycle": cmd_live_cycle,
    "extract": cmd_extract,
    "graphs": cmd_graphs,
    "annotate": cmd_annotate,
    "consolidate": cmd_consolidate,
    "vectorsim": cmd_vectorsim,
    "dom": cmd_dom,
    "review": cmd_review,
    "uncertainty": cmd_uncertainty,
    "register": cmd_register,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.error(f"unknown command: {args.command}")
        return 2
    try:
        return handler(args)
    except Exception as e:  # fail-closed: битый ввод -> JSON-ошибка, exit 2
        print(json.dumps({
            "command": args.command,
            "error": f"{type(e).__name__}: {e}",
            "fail_closed": True,
        }, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
