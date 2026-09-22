#!/usr/bin/env python3
"""run_research.py — кросс-платформенный детерминированный BRICKS-runner.

Python-эквивалент run_research.sh (Linux-only). Ведёт полный конвейер
верификации научного текста кодом:

    BRICK 1  SPLIT        claim-parser (opencode agent) -> claims.json + валидация
    BRICK 2  SEARCH       cascade.py + source-fetcher (agent) -> sources_<id>.json
    BRICK 3  VERDICT      fact-checker (agent) -> verdicts_raw.json + factcheck_guard
    BRICK 3.5 CONTENT     content_verdict.py --no-llm (детерминированный entailment)
    BRICK 4  NUMERIC      numeric_comparator.py + merge_numeric.py
    BRICK 5  EVIDENCE+POST evidence_contract.py + post_processor.py (окончательный вердикт)
    BRICK 6  JUSTIFY      justification_check.py (без обоснования -> OPEN)
    BRICK 7  ESCALATE     escalation.py (stop criteria)
    BRICK 8  TRIBUNAL     judge_brief.py + tribunal-judge (agent)
    BRICK 9  SYNTHESIZE   synthesizer.py + synthesizer (agent) -> final_report.md
    BRICK 10 AUDIT        run/<ts>/summary.json

Принцип №0: LLM производит свидетельства. КОД принимает решения.
Агенты вызываются через `opencode run --agent`; детерминированный слой — Python-скрипты.

Работает на Windows и Linux. Пути берутся из окружения harness
(OPENCODE_HARNESS_ROOT / RESEARCH_SCRIPTS_ROOT / RESEARCH_RULES_PATH),
fallback — относительно этого файла.

Usage:
    python run_research.py <input.txt> [--workspace DIR] [--rules rules.yaml]
                           [--opencode-model MODEL] [--dry-run]
                           [--max-cost-rub 20.0] [--max-iterations 3]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# === Пути (env harness с fallback на относительные) ===
SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS = Path(os.environ.get("RESEARCH_SCRIPTS_ROOT", str(SCRIPT_DIR)))
VERIF = SCRIPTS / "verification"
HARNESS_ROOT = Path(os.environ.get("OPENCODE_HARNESS_ROOT", str(SCRIPT_DIR.parent)))
RULES_DEFAULT = Path(os.environ.get("RESEARCH_RULES_PATH", str(SCRIPTS / "rules_balanced.yaml")))
SHARED = Path(os.environ.get("RESEARCH_SHARED_METHODOLOGY", str(HARNESS_ROOT / "shared" / "research-orchestration-process.md")))

PYTHON = os.environ.get("PYTHON", sys.executable)
PYTHONIO_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

VALID_VERDICTS = ("SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS", "OPEN")


def _log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    if _RUN_DIR:
        (_RUN_DIR / "runner.log").open("a", encoding="utf-8").write(line + "\n")


def _err(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] ERROR: {msg}"
    print(line, file=sys.stderr)
    if _RUN_DIR:
        (_RUN_DIR / "runner.log").open("a", encoding="utf-8").write(line + "\n")


def input_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_py(args: list, timeout: int = 120, check: bool = False) -> subprocess.CompletedProcess:
    """Запуск Python-скрипта с UTF-8 окружением."""
    return subprocess.run(
        [PYTHON, *(str(a) for a in args)],
        capture_output=True, text=True, timeout=timeout,
        env=PYTHONIO_ENV, encoding="utf-8", errors="replace", check=check,
    )


def run_agent(agent: str, prompt: str, model: str, timeout: int = 600,
              retries: int = 2, backoff: tuple = (10, 30)) -> str | None:
    """Вызов субагента через его primary-обёртку (opencode run) с ретраями.

    Субагенты (claim-parser, fact-checker и т.д.) НЕ вызываются через
    `opencode run --agent <subagent>` — это не поддерживается CLI. Каждый
    субагент имеет primary-обёртку `<name>-runner`, которая диспатчит его
    через task-инструмент. Здесь мы вызываем обёртку.
    TD-118: ретраи с backoff при timeout/сетевых сбоях (полza.ai DNS-флапы).
    """
    if _DRY_RUN:
        _log(f"DRY-RUN: пропуск агента {agent}")
        return '{"status":"dry_run"}'
    runner_agent = f"{agent}-runner" if agent not in ("research-orchestrator", "writing-orchestrator", "code-orchestrator") else agent
    opencode_bin = os.environ.get("OPENCODE_BIN", "opencode")
    cmd = [opencode_bin, "run", "--agent", runner_agent, prompt, "--model", model]

    last_err = "unknown"
    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                  env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                  encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            last_err = f"timeout {timeout}s"
            if attempt < retries:
                wait = backoff[min(attempt, len(backoff) - 1)]
                _log(f"агент {agent} timeout ({timeout}s), ретрай {attempt + 1}/{retries} через {wait}s")
                time.sleep(wait)
            continue
        except Exception as e:
            last_err = str(e)[:120]
            if attempt < retries:
                wait = backoff[min(attempt, len(backoff) - 1)]
                _log(f"агент {agent} ошибка ({last_err}), ретрай {attempt + 1}/{retries} через {wait}s")
                time.sleep(wait)
            continue
        if proc.returncode == 0:
            return proc.stdout
        last_err = f"exit {proc.returncode}: {proc.stderr[:200]}"
        if attempt < retries:
            wait = backoff[min(attempt, len(backoff) - 1)]
            _log(f"агент {agent} {last_err}, ретрай {attempt + 1}/{retries} через {wait}s")
            time.sleep(wait)
    _err(f"агент {agent} упал после {retries + 1} попыток ({last_err})")
    (_RUN_DIR / f"{agent}_stderr.log").open("a", encoding="utf-8").write(f"FINAL: {last_err}\n")
    return None


def extract_json(text: str) -> dict | None:
    """Извлечь JSON из вывода агента: ```json блок или первая {...}."""
    if not text:
        return None
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def audit(block: str, decision: str, inp: str, out: str, dur: float, errors: list | None = None) -> None:
    entry = {
        "schema": "research-runner/v1",
        "block": block, "decision": decision,
        "input": inp, "output": out,
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "duration_sec": round(dur, 2),
        "errors": errors or [],
    }
    log_path = _RUN_DIR / "_audit.json"
    data = []
    if log_path.exists():
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            data = []
    data.append(entry)
    log_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_artifact(file: Path, kind: str) -> bool:
    """Блокирующая валидация схемы артефакта (по контракту bash-runner)."""
    if not file.exists():
        _err(f"валидация {kind}: файл не найден {file}")
        return False
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except Exception as e:
        _err(f"валидация {kind}: JSON не читается: {e}")
        return False
    errors = []
    if kind == "claims":
        if not isinstance(data, dict):
            errors.append("корень не dict")
        elif "claims" not in data:
            errors.append("нет ключа 'claims'")
        elif "validated" not in data.get("claims", {}):
            errors.append("нет claims.validated")
        for i, c in enumerate(data.get("claims", {}).get("validated", [])):
            if "text" not in c:
                errors.append(f"claim[{i}]: нет text")
            if "index" not in c:
                errors.append(f"claim[{i}]: нет index")
            if "claim_type" not in c:
                errors.append(f"claim[{i}]: нет claim_type")
            elif c.get("claim_type") not in ("numeric", "qualitative", "definition", "methodological"):
                errors.append(f"claim[{i}]: неверный claim_type '{c.get('claim_type')}'")
    elif kind == "sources":
        if not isinstance(data, dict):
            errors.append("корень не dict")
        for sid, slist in data.items():
            if not isinstance(slist, list):
                errors.append(f"source[{sid}]: не list")
    elif kind == "verdicts":
        verdicts_list = data.get("verdicts", []) if isinstance(data, dict) else data
        if not isinstance(verdicts_list, list):
            errors.append("verdicts: не list")
        for i, v in enumerate(verdicts_list if isinstance(verdicts_list, list) else []):
            if not isinstance(v, dict):
                errors.append(f"verdict[{i}]: не dict")
                continue
            if "verdict" not in v:
                errors.append(f"verdict[{i}]: нет verdict")
            elif v.get("verdict") not in VALID_VERDICTS:
                errors.append(f"verdict[{i}]: неверный verdict '{v.get('verdict')}'")
            if "confidence" in v:
                c = v["confidence"]
                if not isinstance(c, (int, float)) or c < 0.0 or c > 1.0:
                    errors.append(f"verdict[{i}]: confidence={c} вне [0,1]")
    if errors:
        _err(f"VALIDATION FAIL [{kind}]: {errors[:10]}")
        return False
    _log(f"VALIDATION OK [{kind}]: {file}")
    return True


# === BRICKS ===
def brick_split(workspace: Path, model: str) -> int | None:
    _log("BRICK 1: SPLIT — извлечение клаймов")
    t0 = time.time()
    prompt = (f"Прочитай shared-методологию: {SHARED} (секция Контракты данных → Claim). "
              f"Извлеки атомарные клаймы из файла: {_INPUT}. Верни JSON по контракту Claim в СВОЁМ ответе (stdout), "
              f"НЕ пиши файл — runner сам сохранит. Формат: {{status, claims:{{validated:[{{text, original_sentence, "
              f"index, claim_type, importance}}], discarded:[{{text, reason}}]}}, statistics}}.")
    out = run_agent("claim-parser", prompt, model)
    if out is None:
        audit("SPLIT", "FAIL", str(_INPUT), "agent_fail", time.time() - t0, ["agent failed"])
        return None
    if _DRY_RUN:
        _log("  DRY-RUN: claims.json не создаётся")
        audit("SPLIT", "DRY_RUN", str(_INPUT), "none", time.time() - t0)
        return 0
    data = extract_json(out)
    if data is None:
        _err("claims.json: JSON не извлечён из ответа claim-parser")
        (workspace / "run" / _TS / "claim-parser_raw.log").open("a", encoding="utf-8").write(out + "\n")
        audit("SPLIT", "FAIL", str(_INPUT), "parse_fail", time.time() - t0, ["JSON not extracted"])
        return None
    claims_path = workspace / "claims.json"
    claims_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if not validate_artifact(claims_path, "claims"):
        return None
    n = len(data.get("claims", {}).get("validated", []))
    _log(f"  клаймов извлечено: {n}")
    audit("SPLIT", "OK", str(_INPUT), str(claims_path), time.time() - t0)
    return n


def brick_cascade_search(workspace: Path) -> int:
    _log("BRICK 2.0: CASCADE_SEARCH — детерминированный поиск (0 LLM)")
    t0 = time.time()
    cascade_py = VERIF / "cascade.py"
    claims_path = workspace / "claims.json"
    total = 0
    if not claims_path.exists():
        _err("cascade: claims.json отсутствует")
        return 0
    claims = json.loads(claims_path.read_text(encoding="utf-8")).get("claims", {}).get("validated", [])
    for c in claims:
        cid = str(c.get("index"))
        claim_text = c.get("text", "")
        out_file = workspace / f"sources_cascade_{cid}.json"
        try:
            r = run_py([cascade_py, claim_text, "--layers", "local_corpus,openalex,arxiv,web_ddg",
                        "--limit", "4", "--json"], timeout=60)
            if r.returncode != 0:
                _log(f"  claim {cid}: cascade rc={r.returncode}")
                continue
            res = json.loads(r.stdout)
            sources = res.get("sources", [])
            for s in sources:
                if s.get("excerpt") and len(s["excerpt"]) > 2000:
                    s["excerpt"] = s["excerpt"][:2000]
                if s.get("text") and len(s["text"]) > 2000:
                    s["text"] = s["text"][:2000]
            out_file.write_text(json.dumps({"task_id": f"rt_{cid}", "claim_ids": [int(cid)],
                                            "sources": sources, "rejected_sources": []},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
            total += len(sources)
        except Exception as e:
            _log(f"  claim {cid}: cascade exception {e}")
    _log(f"  каскад всего источников: {total}")
    audit("CASCADE_SEARCH", "OK", "claims", "sources_cascade_*", time.time() - t0)
    return total


def brick_search(workspace: Path, model: str) -> None:
    _log("BRICK 2: SEARCH — источник-дополнение (per claim)")
    t0 = time.time()
    brick_cascade_search(workspace)
    claims_path = workspace / "claims.json"
    if not claims_path.exists():
        return
    claims = json.loads(claims_path.read_text(encoding="utf-8")).get("claims", {}).get("validated", [])
    for c in claims:
        cid = str(c.get("index"))
        claim_text = c.get("text", "")
        prompt = (f"Прочитай {SHARED} (секция Source/Evidence + Инструменты + Порядок источников). "
                  f"ResearchTask: claim_id={cid}, claim_text=\"{claim_text}\", "
                  f"question=\"Найди источники (browser_search/webfetch), файл в {workspace}/sources_cascade_{cid}.json "
                  f"(детерминированный каскад уже сделал local_corpus/openalex/arxiv)\", "
                  f"preferred_source_classes=[primary,textbook,review], max_cost_rub=0.5. "
                  f"Не дублируй cascade — только веб. Запиши в {workspace}/sources_{cid}.json (обычным write). "
                  f"Формат source: source_id, title, url, doi, type, trust?[0,1], excerpt?2000, found_via.")
        out = run_agent("source-fetcher", prompt, model)
        if out is None:
            continue
        src_file = workspace / f"sources_{cid}.json"
        if not src_file.exists():
            _err(f"  sources_{cid}.json не создан")
            continue
        # Детерминированный парсер: reject blocked/http/empty_excerpt, clamp trust
        try:
            data = json.loads(src_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        rejected = data.setdefault("rejected_sources", [])
        kept = []
        for s in data.get("sources", []):
            drop = None
            if s.get("blocked") is True or s.get("http_status", 200) >= 400:
                drop = f"blocked/http_{s.get('http_status','?')}"
            elif not s.get("excerpt") or len(str(s["excerpt"]).strip()) < 20:
                drop = "empty_excerpt"
            elif "trust" in s:
                t = s["trust"]
                if not isinstance(t, (int, float)):
                    drop = "trust_not_number"
                else:
                    s["trust"] = max(0.0, min(1.0, float(t)))
            if drop:
                rejected.append({"title": s.get("title", "?"), "reason": drop, "url": s.get("url", "")})
            else:
                kept.append(s)
        data["sources"] = kept
        src_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"  claim {cid}: источников {len(kept)}")
    audit("SEARCH", "OK", "claims", "sources_*", time.time() - t0)


def brick_verdict(workspace: Path, model: str) -> bool:
    _log("BRICK 3: VERDICT — факт-чекинг")
    t0 = time.time()
    prompt = (f"Прочитай {SHARED} (секция Verdict + Принцип №0 + Анти-сикофантия). "
              f"Для каждого клайма из {workspace}/claims.json с источниками {workspace}/sources_*.json: "
              f"сравни клайм с источниками, дай предварительный вердикт (SUPPORTED/CONTRADICTED/UNSUPPORTED/AMBIGUOUS) "
              f"с confidence, reason, justification (2-4 предложения), caveats. Не запускай numeric_comparator.py — это BRICK 4. "
              f"Верни JSON в своём ответе (stdout). Формат: {{verdicts:[{{claim_id, claim_text, verdict, confidence, reason, "
              f"justification, sources_used, caveats, numeric_comparison:{{claim_value, source_value, status}}}}]}}.")
    out = run_agent("fact-checker", prompt, model)
    if out is None:
        audit("VERDICT", "FAIL", "claims", "agent_fail", time.time() - t0, ["agent failed"])
        return False
    if _DRY_RUN:
        _log("  DRY-RUN: verdicts_raw.json не создаётся")
        audit("VERDICT", "DRY_RUN", "claims", "none", time.time() - t0)
        return True
    data = extract_json(out)
    if data is None:
        _err("verdicts_raw.json: JSON не извлечён из ответа fact-checker")
        (workspace / "run" / _TS / "fact-checker_raw.log").open("a", encoding="utf-8").write(out + "\n")
        audit("VERDICT", "FAIL", "claims", "parse_fail", time.time() - t0, ["JSON not extracted"])
        return False
    verdicts_path = workspace / "verdicts_raw.json"
    verdicts_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # factcheck_guard (санитизация LLM-сбоев)
    r = run_py([SCRIPTS / "factcheck_guard.py", verdicts_path, "--mark-parse-fail", "--out", verdicts_path], timeout=60)
    if r.returncode != 0:
        _err(f"factcheck_guard: rc={r.returncode}")
    if not validate_artifact(verdicts_path, "verdicts"):
        return False
    audit("VERDICT", "OK", "claims+sources", str(verdicts_path), time.time() - t0)
    return True


def brick_content_verdict_gate(workspace: Path, model: str) -> None:
    _log("BRICK 3.5: CONTENT_VERDICT_GATE — детерминированный entailment")
    t0 = time.time()
    cv_py = VERIF / "content_verdict.py"
    ws, doc_file = workspace, _INPUT
    claims_path = ws / "claims.json"
    verdicts_path = ws / "verdicts_raw.json"
    if not claims_path.exists() or not verdicts_path.exists():
        return
    claims = json.loads(claims_path.read_text(encoding="utf-8")).get("claims", {}).get("validated", [])
    verdicts_data = json.loads(verdicts_path.read_text(encoding="utf-8"))
    verdicts = verdicts_data.get("verdicts", []) if isinstance(verdicts_data, dict) else verdicts_data
    verdict_by_id = {}
    for v in verdicts:
        cid = v.get("claim_id", v.get("index"))
        if cid is not None:
            verdict_by_id[str(cid)] = v
    gated = 0
    for c in claims:
        cid = str(c.get("index"))
        claim_text = c.get("text", "")
        src_file = ws / f"sources_{cid}.json"
        if not src_file.exists():
            continue
        v = verdict_by_id.get(cid)
        if v is None:
            continue
        try:
            r = run_py([cv_py, claim_text, "--sources", src_file, "--document", doc_file, "--no-llm", "--json"], timeout=30)
            if r.returncode != 0:
                continue
            cv = json.loads(r.stdout)
        except Exception:
            continue
        preds = [p.get("predicate") for p in cv.get("per_source", [])]
        n_supports = sum(1 for p in preds if p == "supports")
        n_refutes = sum(1 for p in preds if p == "refutes")
        n_irrelevant = sum(1 for p in preds if p == "irrelevant")
        n_total = len(preds)
        llm_verdict = v.get("verdict", "")
        det_contradicts = (n_refutes > 0) or (n_supports == 0 and n_total > 0 and n_irrelevant == n_total)
        if llm_verdict == "SUPPORTED" and det_contradicts:
            v["confidence"] = min(v.get("confidence", 0.5), 0.5)
            v["verdict"] = "AMBIGUOUS"
            v.setdefault("caveats", []).append({
                "severity": "critical",
                "text": (f"deterministic_entailment_mismatch: LLM=SUPPORTED, но content_verdict "
                         f"supports={n_supports}, refutes={n_refutes}, irrelevant={n_irrelevant}"),
            })
            v["content_verdict_gate"] = {"action": "downgraded_to_ambiguous", "supports": n_supports,
                                         "refutes": n_refutes, "irrelevant": n_irrelevant}
            gated += 1
        else:
            v["content_verdict_gate"] = {"action": "ok", "supports": n_supports,
                                         "refutes": n_refutes, "irrelevant": n_irrelevant}
    verdicts_path.write_text(json.dumps(verdicts_data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"  content_verdict_gate: gated={gated}")
    audit("CONTENT_VERDICT_GATE", "OK", "verdicts_raw", "verdicts_raw+gates", time.time() - t0)


def brick_numeric(workspace: Path) -> None:
    _log("BRICK 4: NUMERIC — детерминированное числовое сопоставление + MERGE")
    t0 = time.time()
    if not (workspace / "verdicts_raw.json").exists():
        _log("  BRICK 4: verdicts_raw.json отсутствует (dry-run?) — пропуск")
        return
    # sources_index.json
    idx = {}
    for f in workspace.glob("sources_*.json"):
        if "cascade" in f.name or f.name == "sources_index.json":
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            for s in d.get("sources", []):
                sid = s.get("source_id") or s.get("title", "")[:40].lower().replace(" ", "_")
                idx[sid] = s
        except Exception:
            pass
    (workspace / "sources_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"  sources_index: {len(idx)} источников")
    # numeric_comparator
    r = run_py([SCRIPTS / "numeric_comparator.py", workspace / "verdicts_raw.json",
                workspace / "sources_index.json", workspace / "numeric_result.json"], timeout=180)
    if r.returncode != 0:
        _log(f"  numeric_comparator: rc={r.returncode} (не фатально)")
    # merge_numeric
    if (workspace / "numeric_result.json").exists():
        r = run_py([SCRIPTS / "merge_numeric.py", workspace / "verdicts_raw.json",
                    workspace / "numeric_result.json", workspace / "verdicts_enriched.json"], timeout=60)
        if r.returncode != 0:
            _err(f"merge_numeric: rc={r.returncode}")
    else:
        (workspace / "verdicts_enriched.json").write_text(
            (workspace / "verdicts_raw.json").read_text(encoding="utf-8"), encoding="utf-8")
    audit("NUMERIC", "OK", "verdicts_raw", "verdicts_enriched.json", time.time() - t0)


def brick_evidence_post(workspace: Path) -> None:
    _log("BRICK 5: EVIDENCE + POST — окончательный вердикт")
    t0 = time.time()
    if not (workspace / "verdicts_enriched.json").exists():
        _log("  BRICK 5: verdicts_enriched.json отсутствует (dry-run?) — пропуск")
        return
    r = run_py([SCRIPTS / "evidence_contract.py", workspace / "verdicts_enriched.json",
                _RULES, workspace / "evidence_out.json"], timeout=60)
    if r.returncode != 0:
        _err(f"evidence_contract: rc={r.returncode}")
        import shutil
        if (workspace / "verdicts_enriched.json").exists():
            shutil.copy(workspace / "verdicts_enriched.json", workspace / "verdicts_final.json")
        return
    r = run_py([SCRIPTS / "post_processor.py", workspace / "verdicts_enriched.json",
                _RULES, workspace / "verdicts_final.json"], timeout=60)
    if r.returncode != 0:
        _err(f"post_processor: rc={r.returncode}")
    if (workspace / "verdicts_final.json").exists():
        _log("  post_processor: окончательный вердикт готов")
    audit("EVIDENCE_POST", "OK", "enriched", "verdicts_final.json", time.time() - t0)


def brick_justify(workspace: Path) -> None:
    _log("BRICK 6: JUSTIFY — без обоснования → OPEN")
    t0 = time.time()
    if not (workspace / "verdicts_final.json").exists():
        _log("  BRICK 6: verdicts_final.json отсутствует (dry-run?) — пропуск")
        return
    r = run_py([SCRIPTS / "justification_check.py", workspace / "verdicts_final.json",
                _RULES, workspace / "verdicts_final.json", "--report", _RUN_DIR / "alarms.json"], timeout=60)
    if r.returncode != 0:
        _err(f"justification_check: rc={r.returncode}")
    audit("JUSTIFY", "OK", "verdicts_final", "verdicts_final+alarms", time.time() - t0)


def brick_escalate(workspace: Path) -> None:
    _log("BRICK 7: ESCALATE — stop criteria")
    t0 = time.time()
    if not (workspace / "verdicts_final.json").exists():
        _log("  BRICK 7: verdicts_final.json отсутствует (dry-run?) — пропуск")
        return
    topics = workspace / "topics_tree.json"
    if not topics.exists():
        try:
            claims = json.loads((workspace / "claims.json").read_text(encoding="utf-8"))
            ids = [c["index"] for c in claims.get("claims", {}).get("validated", [])]
            tree = {"topics_tree": {"id": "root", "label": "all", "claims": [str(x) for x in ids], "children": []}}
        except Exception:
            tree = {"topics_tree": {"id": "root", "label": "all", "claims": [], "children": []}}
        topics.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run_py([SCRIPTS / "escalation.py", workspace / "verdicts_final.json", topics,
                _RULES, workspace / "escalation_out.json"], timeout=60)
    if r.returncode != 0:
        _err(f"escalation: rc={r.returncode}")
    if (workspace / "escalation_out.json").exists():
        try:
            st = json.loads((workspace / "escalation_out.json").read_text(encoding="utf-8")).get("status", "?")
            _log(f"  escalation status: {st}")
        except Exception:
            pass
    audit("ESCALATE", "OK", "verdicts_final", "escalation_out.json", time.time() - t0)


def brick_tribunal(workspace: Path, model: str) -> None:
    _log("BRICK 8: TRIBUNAL — если триггер")
    t0 = time.time()
    if not (workspace / "verdicts_final.json").exists():
        _log("  BRICK 8: verdicts_final.json отсутствует (dry-run?) — пропуск")
        return
    r = run_py([SCRIPTS / "judge_brief.py", workspace / "verdicts_final.json",
                workspace / "judge_briefs.json"], timeout=60)
    if r.returncode != 0:
        _err(f"judge_brief: rc={r.returncode}")
        audit("TRIBUNAL", "SKIP", "verdicts_final", "no_briefs", time.time() - t0, ["judge_brief failed"])
        return
    tribunal_claims = []
    try:
        d = json.loads((workspace / "verdicts_final.json").read_text(encoding="utf-8"))
        for v in d.get("verdicts", []):
            if v.get("verdict") in ("AMBIGUOUS", "CONTRADICTED") or \
               any(c.get("severity") == "critical" for c in v.get("caveats", [])):
                tribunal_claims.append(str(v.get("claim_id", v.get("index", "?"))))
    except Exception:
        pass
    if not tribunal_claims:
        _log("  трибунал не требуется (нет спорных)")
        audit("TRIBUNAL", "SKIP", "verdicts_final", "no_trigger", time.time() - t0)
        return
    _log(f"  трибунал для: {tribunal_claims}")
    prompt = (f"Прочитай {SHARED} (секция TribunalReport + Триггер трибунала). Брифы судей: {workspace}/judge_briefs.json. "
              f"Вердикты: {workspace}/verdicts_final.json. Для клаймов {tribunal_claims}: проведи трибунал 5 судей "
              f"(физик/методолог/скептик/адвокат/агрегатор), итог, согласованность. Верни JSON в stdout. "
              f"Формат: {{reports: [{{claim_id, judges[], aggregate_verdict, final_confidence, consensus_type, escalation_seed}}]}}.")
    out = run_agent("tribunal-judge", prompt, model)
    if out is None:
        audit("TRIBUNAL", "FAIL", "briefs", "agent_fail", time.time() - t0, ["agent failed"])
        return
    data = extract_json(out)
    if data is not None:
        (workspace / "tribunal_combined.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    audit("TRIBUNAL", "OK", "briefs", "tribunal_combined.json", time.time() - t0)


def brick_synthesize(workspace: Path, model: str) -> None:
    _log("BRICK 9: SYNTHESIZE — финальный отчёт")
    t0 = time.time()
    if not (workspace / "verdicts_final.json").exists():
        _log("  BRICK 9: verdicts_final.json отсутствует (dry-run?) — пропуск")
        return
    tribunal_arg = workspace / "tribunal_combined.json" if (workspace / "tribunal_combined.json").exists() else None
    args = [SCRIPTS / "synthesizer.py", workspace / "verdicts_final.json"]
    if tribunal_arg:
        args.append(tribunal_arg)
    args.append(workspace / "final_report_base.md")
    r = run_py(args, timeout=60)
    if r.returncode != 0:
        _err(f"synthesizer.py: rc={r.returncode}")
    prompt = (f"Прочитай {SHARED} (секция Поток данных + Шкала вердиктов). Базовый отчёт: {workspace}/final_report_base.md. "
              f"Вердикты: {workspace}/verdicts_final.json. Трибунал: {workspace}/tribunal_combined.json (если есть). "
              f"Собери расширенный final_report.md: сводка, таблица по клаймам (цветовая кодировка 🟢🔴🟡🟠⚪), "
              f"проблемные тезисы, вопросы автору (привязка к claim_id), рекомендации. "
              f"Запиши в {workspace}/final_report.md (обычным write).")
    run_agent("synthesizer", prompt, model)
    if (workspace / "final_report.md").exists():
        _log("  final_report.md готов")
    else:
        import shutil
        if (workspace / "final_report_base.md").exists():
            shutil.copy(workspace / "final_report_base.md", workspace / "final_report.md")
    audit("SYNTHESIZE", "OK", "verdicts_final", "final_report.md", time.time() - t0)


def brick_audit(workspace: Path) -> dict:
    _log("BRICK 10: AUDIT — сводка")
    ih = input_hash(_INPUT)
    summary = {
        "schema": "research-runner/v1",
        "input": str(_INPUT),
        "input_hash": ih,
        "workspace": str(workspace),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "budget": {"spent_rub": _BUDGET_SPENT_RUB, "max_rub": _MAX_COST_RUB,
                   "exceeded": _BUDGET_SPENT_RUB > _MAX_COST_RUB},
        "steps": [],
        "artifacts": {
            "claims": (workspace / "claims.json").exists(),
            "verdicts_final": (workspace / "verdicts_final.json").exists(),
            "final_report": (workspace / "final_report.md").exists(),
            "tribunal": (workspace / "tribunal_combined.json").exists(),
            "evidence": (workspace / "evidence_out.json").exists(),
            "numeric": (workspace / "numeric_result.json").exists(),
        },
    }
    audit_path = _RUN_DIR / "_audit.json"
    if audit_path.exists():
        try:
            summary["steps"] = json.loads(audit_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    (_RUN_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("AUDIT записан: " + str(_RUN_DIR / "summary.json"))
    return summary


# === Глобальное состояние (заполняется в main) ===
_INPUT: Path | None = None
_WORKSPACE: Path | None = None
_RULES: Path | None = None
_DRY_RUN = False
_MODEL = "polza/deepseek/deepseek-v4-flash-0731"
_MAX_COST_RUB = 20.0
_MAX_ITER = 3
_TS = ""
_RUN_DIR: Path
_BUDGET_SPENT_RUB = 0.0


def main() -> int:
    global _INPUT, _WORKSPACE, _RULES, _DRY_RUN, _MODEL, _MAX_COST_RUB, _MAX_ITER, _TS, _RUN_DIR, _BUDGET_SPENT_RUB

    ap = argparse.ArgumentParser(description="Deterministic BRICKS research runner (cross-platform)")
    ap.add_argument("input", help="path to input .txt")
    ap.add_argument("--workspace", default=None, help="workspace dir (default: <temp>/research-<ts>)")
    ap.add_argument("--rules", default=None, help="rules yaml (default: RESEARCH_RULES_PATH)")
    ap.add_argument("--opencode-model", default=os.environ.get("OPENCODE_MODEL", "polza/deepseek/deepseek-v4-flash-0731"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-cost-rub", type=float, default=20.0)
    ap.add_argument("--max-iterations", type=int, default=3)
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        print(f"ERROR: файл не найден: {inp}", file=sys.stderr)
        return 2
    _INPUT = inp
    _DRY_RUN = args.dry_run
    _MODEL = args.opencode_model
    _MAX_COST_RUB = args.max_cost_rub
    _MAX_ITER = args.max_iterations

    _RULES = Path(args.rules) if args.rules else RULES_DEFAULT
    if not _RULES.exists():
        print(f"ERROR: rules.yaml не найден: {_RULES}", file=sys.stderr)
        return 2

    _TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.workspace:
        _WORKSPACE = Path(args.workspace)
    else:
        _WORKSPACE = Path(os.environ.get("TEMP", "/tmp")) / f"research-{_TS}"
    _WORKSPACE.mkdir(parents=True, exist_ok=True)
    (_WORKSPACE / "run").mkdir(parents=True, exist_ok=True)
    _RUN_DIR = _WORKSPACE / "run" / _TS
    _RUN_DIR.mkdir(parents=True, exist_ok=True)

    _log(f"=== RUN_RESEARCH START ===")
    _log(f"input: {_INPUT}")
    _log(f"workspace: {_WORKSPACE}")
    _log(f"rules: {_RULES}")
    _log(f"model: {_MODEL}")
    _log(f"input_hash: {input_hash(_INPUT)}")
    _log(f"max_cost_rub: {_MAX_COST_RUB}, max_iterations: {_MAX_ITER}")
    if _DRY_RUN:
        _log("DRY-RUN: агенты не вызываются, скрипты без данных")

    exit_code = 0

    n_claims = brick_split(_WORKSPACE, _MODEL)
    if n_claims is None:
        _err("SPLIT failed")
        exit_code = 1
    _log(f"=== клаймов: {n_claims} ===")

    stop_reason = ""
    iteration = 0
    while iteration < _MAX_ITER and not stop_reason:
        iteration += 1
        _log(f"=== ИТЕРАЦИЯ {iteration}/{_MAX_ITER} ===")
        brick_search(_WORKSPACE, _MODEL)
        if not brick_verdict(_WORKSPACE, _MODEL):
            exit_code = 1
        brick_content_verdict_gate(_WORKSPACE, _MODEL)
        brick_numeric(_WORKSPACE)
        brick_evidence_post(_WORKSPACE)
        brick_justify(_WORKSPACE)
        brick_escalate(_WORKSPACE)

        pending = 0
        vf = _WORKSPACE / "verdicts_final.json"
        if vf.exists():
            try:
                d = json.loads(vf.read_text(encoding="utf-8"))
                pending = sum(1 for v in d.get("verdicts", []) if v.get("verdict") in ("OPEN", "AMBIGUOUS"))
            except Exception:
                pending = 0
        if pending == 0 or iteration >= _MAX_ITER:
            _log(f"  сходимость: pending={pending}, iter={iteration}/{_MAX_ITER} → выход из цикла")
            break
        _log(f"  осталось спорных клаймов: {pending} → повтор SEARCH")
        (_WORKSPACE / f"iteration_{iteration}_pending.txt").write_text(f"  {pending}\n", encoding="utf-8")

    if not stop_reason:
        brick_tribunal(_WORKSPACE, _MODEL)
    brick_synthesize(_WORKSPACE, _MODEL)
    brick_audit(_WORKSPACE)

    _log("=== RUN_RESEARCH END ===")
    _log(f"Результат: {_WORKSPACE}")
    _log(f"Audit: {_RUN_DIR}/summary.json")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())