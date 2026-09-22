# -*- coding: utf-8 -*-
"""writer_core.live_cycle — «живой» цикл фабрики письма (контур кодекра).

    ResearchBundle → claims → WriterContract → draft → re-extraction
        → RTT-diff → constrained repair

Обобщение доказательства run_live_cycle.py на реальных авторефератах:
  v1  -> ResearchBundle (77 claims)
  v8  -> WriterContract (80 разрешённых claims, RTT-эталон)
  v12 -> draft (82 claims) -> re-extraction -> RTT-diff FAIL (17 дефектов:
         1 negation_flip + modality_upgrade-доминанта) -> constrained repair
         (дефект -> claim_id -> span).

Переиспользуемые функции:
  research_bundle_from_path(version_path)   — документ -> ResearchBundleLA;
  writer_contract_from_path(version_path)   — документ -> list[WriterContract]
                                              (эталон разрешённых claims);
  plan_from_topic(topic)                    — тема -> structure_plan.json БЕЗ
                                              документа: каркас из SECTION_REGISTRY
                                              автореферата (11 типов секций,
                                              слоты required_claims/artifacts,
                                              gaps = все слоты). Это то, что
                                              writing-orchestrator (высший ранг)
                                              вызывает ПЕРЕД research: «дерево
                                              для заполнения блоками»;
  run_live_cycle(bundle, contract_path, draft_text, ...) — весь контур
                                              bundle->claims->contract->draft->
                                              rtt->(repair) -> отчёт (dict);
  write_report(report, out_path)            — live_cycle_report.json.

Fail-closed: битый bundle/контракт -> ValueError наружу (CLI превращает в
JSON-ошибку + exit 2). Только stdlib + готовые модули гибрида (hybrid_extract,
structure_annotator, rtt_compare/t0_ru) — без LLM, детерминированно.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or (os.path.dirname(_HERE) if os.path.basename(_HERE) == "writer_core" else _HERE)
_HARNESS_ROOT = os.path.dirname(os.path.dirname(_WC_ROOT))
for _p in (_WC_ROOT, os.path.join(_WC_ROOT, "v2_extractor"), os.path.join(_WC_ROOT, "writer_core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Разумный порядок секций диссертационного автореферата (11 типов
# SECTION_REGISTRY из structure_annotator) — план без документа.
_DEFAULT_SECTION_ORDER: list[str] = [
    "TITLE", "RELEVANCE", "OBJECT_SUBJECT", "TOPIC_STATE", "GOAL",
    "TASKS", "NOVELTY", "METHODS", "RESULTS", "CONCLUSION", "LITERATURE",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _trunc(s: Any, n: int = 80) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:n] + ("..." if len(s) > n else "")


# ---------------------------------------------------------------------------
# 1. документ -> claims / ResearchBundleLA / WriterContract
#    (точно как run_live_cycle.get_claims / v1-bundle / v8-contract)
# ---------------------------------------------------------------------------

def _claims_from_version(version_path: str, max_paragraphs: int = 100) -> list[dict]:
    """Гибридная экстракция документа -> [claim-dict] (claim_id/proposition/
    scope/modality/qa_status/para_id). Префикс claim_id — первые 10 символов
    имени файла (как в доказательстве run_live_cycle).
    """
    from hybrid_extract import hybrid_extract_document  # noqa: F401

    doc = hybrid_extract_document(version_path, max_paragraphs=max_paragraphs)
    prefix = os.path.basename(version_path).split(".")[0][:10]
    claims: list[dict] = []
    for pi, p in enumerate(doc.get("paragraphs") or []):
        digest = p.get("digest") or {}
        for ci, cl in enumerate(p.get("claims") or []):
            claims.append({
                "claim_id": f"{prefix}_{pi}_{ci}",
                "proposition": cl.get("text", ""),
                "scope": digest.get("scope", {}),
                "modality": digest.get("modality"),
                "qa_status": cl.get("qa_status"),
                "para_id": p.get("paragraph_id"),
            })
    return claims


def research_bundle_from_path(version_path: str,
                              max_paragraphs: int = 100) -> "ResearchBundleLA":
    """Документ (docx/pdf/md) -> ResearchBundleLA (роль v1 в контуре).

    Каждый claim документа становится BundleClaim; sources — по одному
    SourceRef на claim (как в run_live_cycle).
    """
    from writer_core.contracts import (  # noqa: F402
        BundleClaim, ResearchBundleLA, SourceRef,
    )

    claims = _claims_from_version(version_path, max_paragraphs=max_paragraphs)
    props = [c for c in claims if c.get("proposition")]
    return ResearchBundleLA(
        task_contract="автореферат кандидатской диссертации "
                      f"(source {os.path.basename(version_path)})",
        sources=[SourceRef(id=f"src_{i}", uri=version_path,
                           title=os.path.basename(version_path))
                 for i in range(len(props))],
        claims=[BundleClaim(claim_id=c["claim_id"],
                            proposition=c["proposition"],
                            source_id=f"src_{i}",
                            qa_status=c.get("qa_status"))
                for i, c in enumerate(props)],
        evidence_links=[], contradictions=[], unresolved_questions=[],
        confidence_map={"n_claims": len(props)},
    )


def writer_contract_from_path(version_path: str,
                              max_paragraphs: int = 100) -> list["WriterContract"]:
    """Документ-эталон -> list[WriterContract] (роль v8: разрешённые claims).

    Каждый proposition документа -> WriterContract с forbidden_transformations
    (все RTT-причины, кроме безопасных) — то, с чем сверяется черновик.
    """
    from writer_core.contracts import writer_contract_from_claim  # noqa: F402

    out: list = []
    for c in _claims_from_version(version_path, max_paragraphs=max_paragraphs):
        if not c.get("proposition"):
            continue
        out.append(writer_contract_from_claim({
            "claim_id": c["claim_id"],
            "text": c["proposition"],
            "modality": c.get("modality"),
            "qa_status": c.get("qa_status"),
        }))
    return out


# ---------------------------------------------------------------------------
# 2. topic -> structure_plan.json БЕЗ документа (каркас до research)
# ---------------------------------------------------------------------------

def select_section_registry(topic: str) -> tuple[dict, str]:
    """Выбор SECTION_REGISTRY по теме (детерминированно).

    В structure_annotator зарегистрирован один реестр — автореферата
    (11 типов секций: discourse_role/argument_role/required_claims/
    required_artifacts/completion). Точка расширения: при добавлении реестров
    других жанров сюда приходит keyword-выбор по теме.
    Возвращает (registry, registry_id).
    """
    from structure_annotator import SECTION_REGISTRY  # noqa: F402
    return SECTION_REGISTRY, "autoreferat"


def plan_from_topic(topic: str,
                    section_order: list[str] | None = None) -> dict:
    """Тема -> structure_plan.json (каркас «дерева для заполнения блоками»).

    Секции в порядке диссертационного автореферата; для каждой секции —
    SectionGoal со слотами required_claims (ClaimSlot) и required_artifacts
    (ArtifactSlot) из SECTION_REGISTRY. Все слоты изначально GAP
    (gaps == числу слотов) — research должен их заполнить.
    """
    from structure_annotator import SECTION_REGISTRY  # noqa: F402

    topic = (topic or "").strip()
    if not topic:
        raise ValueError("plan --topic: тема не может быть пустой")

    registry, registry_id = select_section_registry(topic)
    order = [s for s in (section_order or _DEFAULT_SECTION_ORDER) if s in registry]

    sections: list[dict] = []
    goals: list[dict] = []
    slots: list[dict] = []
    edges: list[dict] = [{"source": "WO_DOC", "target": "DG_DOC",
                          "type": "DECOMPOSES_TO"}]
    dg_children: list[str] = []

    for i, stype in enumerate(order):
        spec = registry[stype]
        sections.append({
            "id": f"SEC_{stype}",
            "type": "section",
            "parent": "DOC",
            "order": i,
            "children": [],
            "section_type": stype,
            "head": None,
            "head_paragraph_id": None,
            "paragraph_ids": [],
            "source": "topic_plan",
        })
        gid = f"SG_{stype}"
        dg_children.append(gid)
        goal: dict = {
            "id": gid,
            "type": "SectionGoal",
            "parent": "DG_DOC",
            "order": i,
            "children": [],
            "section_type": stype,
            "discourse_role": spec.get("discourse_role"),
            "required_claims": list(spec.get("required_claims", [])),
            "required_artifacts": list(spec.get("required_artifacts", [])),
        }
        for claim in spec.get("required_claims", []):
            sid = f"CS_{stype}_{claim}"
            slots.append({"id": sid, "type": "ClaimSlot", "parent": gid,
                          "order": len(goal["children"]), "section": stype,
                          "kind": "claim", "expected": claim})
            goal["children"].append(sid)
            edges.append({"source": gid, "target": sid, "type": "REQUIRES"})
        for art in spec.get("required_artifacts", []):
            sid = f"AS_{stype}_{art}"
            slots.append({"id": sid, "type": "ArtifactSlot", "parent": gid,
                          "order": len(goal["children"]), "section": stype,
                          "kind": "artifact", "expected": art})
            goal["children"].append(sid)
            edges.append({"source": gid, "target": sid, "type": "REQUIRES"})
        goals.append(goal)

    gaps = [{
        "slot_id": s["id"], "section": s["section"], "kind": s["kind"],
        "expected": s["expected"], "status": "GAP", "severity": "WORK_BLOCKING",
        "research_request": True,
        "note": f"требуется {s['expected']} — слот каркаса plan --topic, "
                f"research ещё не заполнил (секция {s['section']})",
    } for s in slots]

    section_status: dict[str, str] = {}
    for stype in order:
        spec = registry[stype]
        n_slots = len(spec.get("required_claims", [])) + \
            len(spec.get("required_artifacts", []))
        section_status[stype] = "GAP" if n_slots else "N/A"

    return {
        "schema": "writer_core.structure_plan.v1",
        "generated_by": "writer_core.cli.plan.topic",
        "source": {"kind": "topic", "topic": topic, "registry": registry_id},
        "sections": sections,
        "plan": {
            "writing_objective": {"id": "WO_DOC", "type": "WritingObjective",
                                  "parent": None, "order": 0,
                                  "children": ["DG_DOC"]},
            "document_goal": {"id": "DG_DOC", "type": "DocumentGoal",
                              "parent": "WO_DOC", "order": 0,
                              "children": dg_children},
            "goals": goals, "slots": slots, "edges": edges,
        },
        "slots": slots,
        "gaps": gaps,
        "satisfies": [],
        "section_status": section_status,
        "meta": {"topic": topic, "registry": registry_id,
                 "n_sections": len(sections), "n_slots": len(slots),
                 "n_gaps": len(gaps), "errors": []},
    }


# ---------------------------------------------------------------------------
# 3. нормализация входа run_live_cycle (fail-closed)
# ---------------------------------------------------------------------------

def _resolve_bundle(bundle: Any) -> "ResearchBundleLA":
    """ResearchBundleLA | dict | путь к .json -> ResearchBundleLA."""
    from writer_core.contracts import ResearchBundleLA  # noqa: F402

    if isinstance(bundle, ResearchBundleLA):
        return bundle
    if isinstance(bundle, dict):
        return ResearchBundleLA.model_validate(bundle)
    if isinstance(bundle, str):
        if not os.path.exists(bundle):
            raise ValueError(f"live-cycle: файл bundle не найден: {bundle}")
        with open(bundle, "r", encoding="utf-8-sig") as fh:
            return ResearchBundleLA.model_validate(json.load(fh))
    raise ValueError(f"live-cycle: bundle не распознан ({type(bundle).__name__})")


def _resolve_contract(contract_path: Any) -> list[dict]:
    """Путь к .json (writing_contract) | путь к документу | list[claims]
    -> list[dict] WriterContract-полей.

    Автодетекция: .json -> writing_contract (load_contract_claims);
    иначе документ-эталон (docx/pdf/md) -> writer_contract_from_path;
    иначе считаем, что передан готовый список claims.
    """
    from writer_core.factory_process import load_contract_claims  # noqa: F402

    if isinstance(contract_path, str):
        if not os.path.exists(contract_path):
            raise ValueError(f"live-cycle: файл контракта не найден: "
                             f"{contract_path}")
        if contract_path.lower().endswith(".json"):
            with open(contract_path, "r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
            return load_contract_claims(data)
        # документ-эталон: claims -> WriterContract (как v8 в run_live_cycle)
        return [c.model_dump() for c in writer_contract_from_path(contract_path)]
    return load_contract_claims(contract_path)


def _span_of(d: Any) -> list[int] | None:
    """[start, end] из дефекта (span dict или list/tuple) либо None."""
    sp = d.get("span") if isinstance(d, dict) else getattr(d, "span", None)
    if isinstance(sp, dict):
        s, e = sp.get("start"), sp.get("end")
        if isinstance(s, int) and isinstance(e, int):
            return [s, e]
    if isinstance(sp, (list, tuple)) and len(sp) >= 2:
        s, e = sp[0], sp[1]
        if isinstance(s, int) and isinstance(e, int):
            return [s, e]
    return None


# ---------------------------------------------------------------------------
# 4. run_live_cycle — весь контур кодекра
# ---------------------------------------------------------------------------

def run_live_cycle(bundle: Any, contract_path: Any, draft_text: str,
                   max_contract_claims: int | None = 40,
                   repair: bool = False) -> dict:
    """Полный «живой» цикл фабрики письма -> отчёт (dict).

    bundle         — ResearchBundleLA | dict | путь к .json (роль v1);
    contract_path  — writing_contract.json | документ-эталон (роль v8) |
                     list[dict] claims;
    draft_text     — текст черновика (роль v12);
    max_contract_claims — лимит claims контракта для RTT (по умолчанию 40 —
                     ровно как в доказательстве run_live_cycle, даёт 17
                     дефектов; None = все claims);
    repair         — применить constrained repair ко ВСЕМ дефектам и
                     перепроверить черновик.

    Отчёт: research_bundle / writer_contract / draft (re-extraction) /
    rtt_diff (verdict, n_defects, defects_by_type, defects_summary) /
    constrained_repair_demo (первый дефект) / repair (если repair=True).
    """
    from writer_core.factory_process import (  # noqa: F402
        apply_constrained_repair, draftcheck,
    )

    rb = _resolve_bundle(bundle)
    contract_all = _resolve_contract(contract_path)
    if not contract_all:
        raise ValueError("live-cycle: пустой список claims контракта")
    contract_claims = contract_all
    if max_contract_claims is not None:
        contract_claims = contract_all[:int(max_contract_claims)]
    if not contract_claims:
        raise ValueError("live-cycle: max_contract_claims=0 — нечего сверять")

    report: dict = {
        "schema": "writer_core.live_cycle_report.v1",
        "generated_by": "writer_core.live_cycle.run_live_cycle",
        "created_at": _utc_now_iso(),
        "inputs": {
            "bundle": (os.path.normpath(bundle) if isinstance(bundle, str)
                       else f"inline({type(bundle).__name__})"),
            "contract": (os.path.normpath(contract_path)
                         if isinstance(contract_path, str)
                         else f"inline({type(contract_path).__name__})"),
            "draft_chars": len(draft_text or ""),
            "max_contract_claims": max_contract_claims,
        },
        "research_bundle": {
            "n_claims": len(rb.claims),
            "sample": [{"claim_id": c.claim_id,
                        "proposition": _trunc(c.proposition)}
                       for c in rb.claims[:3]],
        },
        "writer_contract": {
            "n_claims": len(contract_all),
            "n_claims_used": len(contract_claims),
            "sample": [{"claim_id": c.get("claim_id"),
                        "proposition": _trunc(c.get("proposition")),
                        "modality": c.get("modality")}
                       for c in contract_claims[:3]],
        },
    }

    # draft -> re-extraction -> RTT-diff против contract (роль v12 vs v8)
    rtt = draftcheck(draft_text or "", contract_claims)
    defects = rtt.get("defects") or []
    report["draft"] = {
        "n_claims_extracted": len((rtt.get("re_extraction") or {})
                                  .get("claims") or []),
    }
    defects_by_type: dict[str, int] = {}
    for d in defects:
        defects_by_type[d.get("defect_type")] = \
            defects_by_type.get(d.get("defect_type"), 0) + 1
    report["rtt_diff"] = {
        "verdict": rtt.get("verdict"),
        "n_defects": len(defects),
        "defects_by_type": defects_by_type,
        "defects_summary": [{
            "type": d.get("defect_type"),
            "claim": d.get("claim_id"),
            "span": _span_of(d),
            "suggestion": (d.get("suggestion") or "")[:150],
        } for d in defects],
    }

    # constrained repair demo (первый дефект) — как в run_live_cycle
    if defects:
        d0 = defects[0]
        sp = _span_of(d0) or [0, 0]
        fixed = apply_constrained_repair(
            draft_text or "",
            [d0])["text"]
        report["constrained_repair_demo"] = {
            "defect": {"type": d0.get("defect_type"),
                       "claim": d0.get("claim_id"),
                       "span": sp},
            "suggestion": (d0.get("suggestion") or "")[:150],
            "repaired": fixed != (draft_text or ""),
        }
    else:
        report["constrained_repair_demo"] = None

    # полный constrained repair + повторный draftcheck (опция --repair)
    if repair:
        repaired = apply_constrained_repair(draft_text or "", defects)
        after = draftcheck(repaired["text"], contract_claims)
        report["repair"] = {
            "ran": True,
            "applied": repaired["applied"],
            "skipped": repaired["skipped"],
            "changed": repaired["text"] != (draft_text or ""),
            "verdict_after": after.get("verdict"),
            "n_defects_after": len(after.get("defects") or []),
            "text": repaired["text"],
        }
    return report


def write_report(report: dict, out_path: str) -> None:
    """Отчёт -> live_cycle_report.json (UTF-8, ensure_ascii=False)."""
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(json.dumps({
        "module": "writer_core.live_cycle",
        "functions": ["research_bundle_from_path", "writer_contract_from_path",
                      "select_section_registry", "plan_from_topic",
                      "run_live_cycle", "write_report"],
    }, ensure_ascii=False, indent=2))
