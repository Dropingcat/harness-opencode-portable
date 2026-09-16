"""Tech-debt scanner for Researcher Core.

The scanner makes shortcuts visible early. It does not try to prove code
quality; it records explicit debt markers and suspicious hardcoded constants so
that interim simplifications are documented in one place.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from researcher_core.policy import load_bootstrap_policy


DEFAULT_INCLUDE_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".toml"}
SEVERITY_ORDER = {"critical": 3, "high": 2, "medium": 1}  # debt-scan: ignore-line

MARKER_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("critical", "not_implemented", r"\b(NotImplementedError|NotImplemented)\b"),  # debt-scan: ignore-line
    ("critical", "pass_statement", r"^\s*pass\s*(#.*)?$"),
    ("high", "stub_marker", r"\b(STUB|stub|заглушк[аи])\b"),  # debt-scan: ignore-line
    ("high", "temporary_marker", r"\b(TEMP|temporary|временно|упрощ[её]нн?)\b"),  # debt-scan: ignore-line
    ("medium", "todo_marker", r"\b(TODO|FIXME|XXX|HACK)\b"),  # debt-scan: ignore-line
)

CODE_SUFFIXES = {".py"}
ALLOWED_NUMBER_LINE_RE = re.compile(
    r"(version|schema_version|line|lines|offset|port|http|https|sha256|pytest|python|>=|<=|==|!=)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DebtFinding:
    path: str
    line: int
    severity: str
    kind: str
    message: str
    excerpt: str


def iter_files(
    root: Path,
    suffixes: set[str] | None = None,
    excluded_files: frozenset[str] | None = None,
    excluded_dirs: frozenset[str] | None = None,
) -> Iterable[Path]:
    suffixes = suffixes or DEFAULT_INCLUDE_SUFFIXES
    excluded_files = excluded_files or frozenset()
    excluded_dirs = excluded_dirs or frozenset()
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if path.name in excluded_files:
            continue
        if any(part in excluded_dirs for part in path.parts):
            continue
        if path.suffix.lower() in suffixes:
            yield path


def _line_is_ignored(line: str) -> bool:
    return "debt-scan: ignore-line" in line


def scan_python_numbers(path: Path, text: str, root: Path) -> list[DebtFinding]:
    findings: list[DebtFinding] = []
    rel = path.relative_to(root).as_posix()
    lines = text.splitlines()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type != tokenize.NUMBER:
                continue
            line_no = token.start[0]
            line = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
            if _line_is_ignored(line) or ALLOWED_NUMBER_LINE_RE.search(line):
                continue
            number = token.string
            if number in {"0", "1"}:
                continue
            findings.append(
                DebtFinding(
                    path=rel,
                    line=line_no,
                    severity="medium",
                    kind="possible_magic_number",
                    message=f"numeric literal {number!r} should be named or policy-backed if epistemic/runtime heuristic",
                    excerpt=line.strip()[:240],
                )
            )
    except tokenize.TokenError as exc:
        findings.append(
            DebtFinding(
                path=rel,
                line=0,
                severity="high",
                kind="tokenize_error",
                message=str(exc),
                excerpt="",
            )
        )
    return findings


def scan_text(path: Path, text: str, root: Path) -> list[DebtFinding]:
    findings: list[DebtFinding] = []
    rel = path.relative_to(root).as_posix()
    in_fenced_block = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if path.suffix.lower() in {".md", ".markdown"} and line.strip().startswith("```"):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block:
            continue
        if _line_is_ignored(line):
            continue
        for severity, kind, pattern in MARKER_PATTERNS:
            if re.search(pattern, line):
                findings.append(
                    DebtFinding(
                        path=rel,
                        line=line_no,
                        severity=severity,
                        kind=kind,
                        message="explicit debt marker must be tracked in policy/config or issue log",
                        excerpt=line.strip()[:240],
                    )
                )

    if path.suffix.lower() in CODE_SUFFIXES:
        findings.extend(scan_python_numbers(path, text, root))
    return findings


def scan_paths(paths: Sequence[Path], root: Path) -> list[DebtFinding]:
    findings: list[DebtFinding] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(
                DebtFinding(
                    path=path.relative_to(root).as_posix(),
                    line=0,
                    severity="critical",
                    kind="read_error",
                    message=str(exc),
                    excerpt="",
                )
            )
            continue
        findings.extend(scan_text(path, text, root))
    return findings


def build_report(root: Path, findings: Sequence[DebtFinding]) -> dict:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return {
        "schema_version": "researcher-debt-report/0.1",
        "root": str(root),
        "counts": counts,
        "total": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan repository for visible technical debt markers.")
    parser.add_argument("root", nargs="?", default=".", help="Repository root to scan")
    parser.add_argument("--json", dest="json_path", help="Write JSON report to this path")
    parser.add_argument(
        "--fail-on",
        choices=["critical", "high", "medium", "none"],
        default="critical",
        help="Return non-zero if findings at this severity or higher exist",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    policy = load_bootstrap_policy(root)
    fail_on = policy.debt_fail_on if args.fail_on == "critical" else args.fail_on
    findings = scan_paths(list(iter_files(root, excluded_files=policy.debt_excluded_files, excluded_dirs=policy.debt_excluded_dirs)), root)
    report = build_report(root, findings)

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_path:
        Path(args.json_path).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    if fail_on == "none":
        return 0
    threshold = SEVERITY_ORDER[fail_on]
    return 1 if any(SEVERITY_ORDER[f.severity] >= threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
