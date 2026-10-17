#!/usr/bin/env python3
"""Детерминированный валидатор контрактов фабрики кода."""

import json
import sys
from pathlib import Path

WORKER_SCHEMA = {"required": ["module", "code", "description", "written_by"]}
REVIEWER_SCHEMA = {
    "required": ["module", "verdict", "comments", "written_by", "verified_by_commands"],
    "verdict_enum": ["APPROVE", "REQUEST_CHANGES"],
    "comments_require": ["file", "line", "problem", "suggestion", "falsification"],
}
TESTER_SCHEMA = {"required": ["module", "result", "passed", "failed", "coverage", "written_by"]}
AUDITOR_SCHEMA = {
    "required": ["verdict", "justification", "process_analysis", "audit_mode", "written_by", "verified_by_commands"],
    "verdict_enum": ["APPROVE", "REJECT", "REQUEST_CHANGES", "INVALID_INPUT"],
    "process_analysis_require": ["contracts_respected", "iteration_count", "iteration_limit", "role_violation"],
    "audit_mode_enum": ["A", "B"],
}
EXPERIMENTER_SCHEMA = {"required": ["metric", "baseline", "best_result", "experiments", "written_by"]}
PLANNER_SCHEMA = {
    "required": [
        "role", "project_id", "level", "input_level", "pipeline", "sections", "written_by",
    ],
    "input_level_enum": ["L0", "L1", "L2", "L3", "L4"],
    "pipeline_enum": ["P1", "P2", "P3", "P4", "P5"],
    "sections_require": [
        "section_1_input_level_and_pipeline",
        "section_2_input_audit",
        "section_3_stages",
        "section_4_resources",
        "section_5_recommendation",
    ],
}
DEPLOYER_SCHEMA = {
    "required": ["role", "project_id", "verdict", "written_by"],
    "verdict_enum": ["DEPLOYED", "BLOCKED"],
}


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_written_by(data: dict, agent_type: str, errors: list[str]) -> None:
    """Защита подмены звена (TD-FACTORY-5): written_by обязан совпадать с agent_type.

    Проверка вызывается из validate() для ВСЕХ agent_type, поэтому required-поля
    `written_by` есть во всех схемах.
    """
    wb = data.get("written_by")
    if wb != agent_type:
        errors.append(f"role substitution: written_by={wb!r} != agent_type={agent_type!r}")


def _check_verified_by_commands(data: dict, agent_type: str, errors: list[str]) -> None:
    """TD-FACTORY-3 (P4): verified_by_commands — непустой список непустых строк.

    Отсутствие поля уже покрывается required-проверкой в validate(), здесь —
    только контентная валидация.
    """
    field = "verified_by_commands"
    v = data.get(field)
    if v is None:
        return
    if not isinstance(v, list) or not v:
        errors.append(f"{agent_type}.{field}: must be non-empty list of strings (P4)")
        return
    for i, cmd in enumerate(v):
        if not isinstance(cmd, str) or not cmd.strip():
            errors.append(f"{agent_type}.{field}[{i}]: must be non-empty string (P4)")


def validate_worker(data: dict) -> list[str]:
    errors = []
    if not data.get("module"):
        errors.append("worker.module: missing/empty")
    if not data.get("code"):
        errors.append("worker.code: missing/empty")
    if not data.get("description"):
        errors.append("worker.description: missing/empty")
    return errors


def validate_reviewer(data: dict) -> list[str]:
    errors = []
    if not data.get("module"):
        errors.append("reviewer.module: missing/empty")
    verdict = data.get("verdict")
    if verdict not in REVIEWER_SCHEMA["verdict_enum"]:
        errors.append(f"reviewer.verdict: must be one of {REVIEWER_SCHEMA['verdict_enum']}, got {verdict!r}")
    comments = data.get("comments")
    if not isinstance(comments, list) or not comments:
        errors.append("reviewer.comments: must be non-empty list")
    else:
        for i, c in enumerate(comments):
            if not isinstance(c, dict):
                errors.append(f"reviewer.comments[{i}]: must be object")
                continue
            for field in REVIEWER_SCHEMA["comments_require"]:
                if field not in c or c[field] in (None, ""):
                    errors.append(f"reviewer.comments[{i}].{field}: missing/empty")
            fals = c.get("falsification")
            if not fals or len(str(fals).strip()) < 5:
                errors.append(f"reviewer.comments[{i}].falsification: too short (<5 chars)")
            # scope-дисциплина: комментарий обязан относиться к scope модуля
            if c.get("out_of_scope") not in (True, None):
                errors.append(f"reviewer.comments[{i}].out_of_scope: must be boolean or omitted")
    gaps = data.get("out_of_scope_gaps")
    if gaps is not None:
        if not isinstance(gaps, list):
            errors.append("reviewer.out_of_scope_gaps: must be a list")
        else:
            for i, g in enumerate(gaps):
                if not isinstance(g, dict):
                    errors.append(f"reviewer.out_of_scope_gaps[{i}]: must be object")
                    continue
                if not g.get("module"):
                    errors.append(f"reviewer.out_of_scope_gaps[{i}].module: missing")
                if not g.get("finding"):
                    errors.append(f"reviewer.out_of_scope_gaps[{i}].finding: missing")
    scope = data.get("scope_declared")
    if scope is not None and not isinstance(scope, dict):
        errors.append("reviewer.scope_declared: must be an object {scope_in, scope_out}")
    _check_verified_by_commands(data, "reviewer", errors)
    return errors


def validate_tester(data: dict) -> list[str]:
    errors = []
    if not data.get("module"):
        errors.append("tester.module: missing/empty")
    result = data.get("result")
    if result not in ("PASS", "FAIL"):
        errors.append(f"tester.result: must be PASS or FAIL, got {result!r}")
    if not _is_number(data.get("passed")):
        errors.append("tester.passed: must be number")
    if not _is_number(data.get("failed")):
        errors.append("tester.failed: must be number")
    cov = data.get("coverage")
    if not _is_number(cov) or not (0 <= cov <= 100):
        errors.append("tester.coverage: must be number 0-100")
    return errors


def validate_auditor(data: dict) -> list[str]:
    errors = []
    verdict = data.get("verdict")
    if verdict not in AUDITOR_SCHEMA["verdict_enum"]:
        errors.append(f"auditor.verdict: must be one of {AUDITOR_SCHEMA['verdict_enum']}, got {verdict!r}")
    # TD-FACTORY-2 (P3): audit_mode обязателен и ∈ {A, B}
    am = data.get("audit_mode")
    if am not in AUDITOR_SCHEMA["audit_mode_enum"]:
        errors.append(
            f"auditor.audit_mode: must be 'A' or 'B' (P3), got {am!r}"
        )
    just = data.get("justification")
    if not just or len(str(just).strip()) < 20:
        errors.append("auditor.justification: too short (<20 chars)")
    pa = data.get("process_analysis")
    if not isinstance(pa, dict):
        errors.append("auditor.process_analysis: must be object")
    else:
        for field in AUDITOR_SCHEMA["process_analysis_require"]:
            if field not in pa:
                errors.append(f"auditor.process_analysis.{field}: missing")
        if not isinstance(pa.get("contracts_respected"), bool):
            errors.append("auditor.process_analysis.contracts_respected: must be bool")
        if not _is_number(pa.get("iteration_count")):
            errors.append("auditor.process_analysis.iteration_count: must be number")
        if not _is_number(pa.get("iteration_limit")):
            errors.append("auditor.process_analysis.iteration_limit: must be number")
        if not isinstance(pa.get("role_violation"), bool):
            errors.append("auditor.process_analysis.role_violation: must be bool")
    _check_verified_by_commands(data, "auditor", errors)
    return errors


def validate_experimenter(data: dict) -> list[str]:
    errors = []
    if not data.get("metric"):
        errors.append("experimenter.metric: missing/empty")
    if not _is_number(data.get("baseline")):
        errors.append("experimenter.baseline: must be number")
    if not _is_number(data.get("best_result")):
        errors.append("experimenter.best_result: must be number")
    exp = data.get("experiments")
    if not isinstance(exp, dict) or not exp:
        errors.append("experimenter.experiments: must be non-empty object")
    return errors


def validate_planner(data: dict) -> list[str]:
    """TD-FACTORY-6 (P5): planner — входы L0-L4 → pipeline P1-P5 (контракт 18)."""
    errors = []
    if not data.get("role"):
        errors.append("planner.role: missing/empty")
    if not data.get("project_id"):
        errors.append("planner.project_id: missing/empty")
    if not data.get("level"):
        errors.append("planner.level: missing/empty")
    il = data.get("input_level")
    if il not in PLANNER_SCHEMA["input_level_enum"]:
        errors.append(f"planner.input_level: must be one of {PLANNER_SCHEMA['input_level_enum']}, got {il!r}")
    pipe = data.get("pipeline")
    if pipe not in PLANNER_SCHEMA["pipeline_enum"]:
        errors.append(f"planner.pipeline: must be one of {PLANNER_SCHEMA['pipeline_enum']}, got {pipe!r}")
    sections = data.get("sections")
    if not isinstance(sections, dict) or not sections:
        errors.append("planner.sections: must be non-empty object")
    else:
        for name in PLANNER_SCHEMA["sections_require"]:
            if name not in sections:
                errors.append(f"planner.sections.{name}: missing required section")
        # связность: section_1 обязан содержать level и input_level
        s1 = sections.get("section_1_input_level_and_pipeline")
        if isinstance(s1, dict):
            if s1.get("level") != data.get("level"):
                errors.append("planner.sections.section_1_input_level_and_pipeline.level: must match top-level level")
            if s1.get("input_level") != il:
                errors.append("planner.sections.section_1_input_level_and_pipeline.input_level: must match top-level input_level")
        elif "section_1_input_level_and_pipeline" in data.get("sections", {}):
            errors.append("planner.sections.section_1_input_level_and_pipeline: must be object")
    return errors


def validate_deployer(data: dict) -> list[str]:
    """TD-FACTORY-4 (P2): deployer — verdict DEPLOYED|BLOCKED; при DEPLOYED — commits/files."""
    errors = []
    if not data.get("role"):
        errors.append("deployer.role: missing/empty")
    if not data.get("project_id"):
        errors.append("deployer.project_id: missing/empty")
    verdict = data.get("verdict")
    if verdict not in DEPLOYER_SCHEMA["verdict_enum"]:
        errors.append(f"deployer.verdict: must be one of {DEPLOYER_SCHEMA['verdict_enum']}, got {verdict!r}")
    if verdict == "DEPLOYED":
        commits = data.get("commits")
        if not isinstance(commits, list) or not commits:
            errors.append("deployer.commits: must be non-empty list when verdict=DEPLOYED")
        files = data.get("files")
        if not isinstance(files, list):
            errors.append("deployer.files: must be list when verdict=DEPLOYED")
    return errors


VALIDATORS = {
    "worker": validate_worker,
    "reviewer": validate_reviewer,
    "tester": validate_tester,
    "auditor": validate_auditor,
    "experimenter": validate_experimenter,
    "planner": validate_planner,
    "deployer": validate_deployer,
}

SCHEMAS = {
    "worker": WORKER_SCHEMA,
    "reviewer": REVIEWER_SCHEMA,
    "tester": TESTER_SCHEMA,
    "auditor": AUDITOR_SCHEMA,
    "experimenter": EXPERIMENTER_SCHEMA,
    "planner": PLANNER_SCHEMA,
    "deployer": DEPLOYER_SCHEMA,
}


def validate(agent_type: str, data: dict) -> list[str]:
    if agent_type not in VALIDATORS:
        return [f"unknown agent_type: {agent_type}"]
    if not isinstance(data, dict):
        return [f"{agent_type}: output must be JSON object, got {type(data).__name__}"]
    errors = []
    for field in SCHEMAS[agent_type]["required"]:
        if field not in data:
            errors.append(f"{agent_type}.{field}: missing required field")
    errors.extend(VALIDATORS[agent_type](data))
    # TD-FACTORY-5: защита подмены звена — для всех agent_type
    _check_written_by(data, agent_type, errors)
    return errors


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: contract_validator.py <agent_type> <output.json>")
        return 2
    agent_type = sys.argv[1]
    path = sys.argv[2]
    if not Path(path).exists():
        print(f"ERROR: file not found: {path}")
        return 2
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {path}: {e}")
        return 2
    errors = validate(agent_type, data)
    if errors:
        print(f"INVALID ({agent_type}):")
        for e in errors:
            print(f"  - {e}")
        return 2
    print(f"VALID ({agent_type})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
