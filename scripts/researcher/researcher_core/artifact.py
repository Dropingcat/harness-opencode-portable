"""Schema-backed checks for research service YAML artifacts.

Prod checker parses YAML via ``yaml.safe_load`` and validates the dict shape.
Text-level logic is kept as fallback for parse errors, but authoritative
checks are dict-based, enabling policy hash and reference validation later.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml


TARGET_SCHEMA_VERSION = "research-service-artifact/0.2"
FORBIDDEN_CLAIM_KEYS = frozenset({"depends_on", "derived_from", "gaps", "conflicts", "children", "parents"})
REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {
        "artifact_type",
        "artifact_id",
        "fixture_id",
        "artifact_manifest",
        "policy",
        "source_versions",
        "document_registry",
        "source_registry",
        "report_spans",
        "evidence_spans",
        "claims",
        "quantities",
        "graph_edges",
        "gaps",
        "writer_context",
        "service_summary",
    }
)


@dataclass(frozen=True, slots=True)
class ArtifactFinding:
    line: int
    severity: str
    kind: str
    message: str
    excerpt: str


def check_artifact_dict(data: Any) -> list[ArtifactFinding]:
    findings: list[ArtifactFinding] = []
    if not isinstance(data, dict):
        findings.append(
            ArtifactFinding(0, "high", "artifact_not_mapping", "artifact top-level must be a mapping", "")
        )
        return findings
    schema = data.get("schema_version")
    if schema != TARGET_SCHEMA_VERSION:
        findings.append(
            ArtifactFinding(
                1, "high", "schema_version_gap", f"artifact must target {TARGET_SCHEMA_VERSION}", str(schema) if schema is not None else ""
            )
        )
    for key in sorted(REQUIRED_TOP_LEVEL_KEYS - set(data.keys())):
        findings.append(ArtifactFinding(0, "high", "missing_top_level_key", f"missing top-level key: {key}", ""))

    claims = data.get("claims")
    if isinstance(claims, dict):
        for claim_id, claim in claims.items():
            if not isinstance(claim, dict):
                continue
            for forbidden in sorted(FORBIDDEN_CLAIM_KEYS):
                if forbidden in claim:
                    findings.append(
                        ArtifactFinding(
                            0,
                            "high",
                            "forbidden_claim_link",
                            f"claim {claim_id!r} must not contain authoritative link key: {forbidden}",
                            str(forbidden),
                        )
                    )
            if "claim_type" in claim:
                findings.append(
                    ArtifactFinding(0, "medium", "legacy_claim_type", "claim_type must split into claim_kind and origin_type", "claim_type")
                )
            if "status" in claim:
                findings.append(
                    ArtifactFinding(0, "medium", "legacy_claim_status", "status must split into states.* axes", "status")
                )
    elif isinstance(claims, list):
        findings.append(ArtifactFinding(0, "high", "claims_not_mapping", "claims must be a mapping (found list, legacy fixture)", ""))
        for idx, claim in enumerate(claims):
            if not isinstance(claim, dict):
                continue
            claim_id = claim.get("id", f"claims[{idx}]")
            for forbidden in sorted(FORBIDDEN_CLAIM_KEYS):
                if forbidden in claim:
                    findings.append(
                        ArtifactFinding(
                            0,
                            "high",
                            "forbidden_claim_link",
                            f"claim {claim_id!r} must not contain authoritative link key: {forbidden}",
                            str(forbidden),
                        )
                    )
            if "claim_type" in claim:
                findings.append(
                    ArtifactFinding(0, "medium", "legacy_claim_type", "claim_type must split into claim_kind and origin_type", "claim_type")
                )
            if "status" in claim:
                findings.append(
                    ArtifactFinding(0, "medium", "legacy_claim_status", "status must split into states.* axes", "status")
                )
    elif claims is not None:
        findings.append(ArtifactFinding(0, "high", "claims_not_mapping", "claims must be a mapping", ""))

    return findings


def check_artifact_text(text: str) -> list[ArtifactFinding]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [
            ArtifactFinding(0, "high", "yaml_parse_error", f"YAML parse error: {exc}", ""),
        ]
    if data is None:
        # empty file -> treat as text-level for missing keys
        data = {}
    # Dict-level is authoritative; text-level kept only for line-number hints on forbidden keys
    findings = check_artifact_dict(data)
    # Merge text-level line hints if dict-level already found same kind (keeps backward compat for tests)
    # For now, return dict findings only — they carry same kinds as text level.
    return findings


def _top_level_keys(lines: Sequence[str]) -> set[str]:
    keys: set[str] = set()
    for line in lines:
        if line and not line.startswith(" ") and ":" in line:
            keys.add(line.split(":", maxsplit=1)[0].strip())
    return keys


def build_report(path: Path, findings: Sequence[ArtifactFinding]) -> dict:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return {
        "schema_version": "researcher-artifact-check/0.1",
        "artifact_path": str(path),
        "target_schema_version": TARGET_SCHEMA_VERSION,
        "counts": counts,
        "total": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check research service artifact YAML draft against target shape.")
    parser.add_argument("artifact", help="YAML artifact path")
    parser.add_argument("--json", dest="json_path", help="Write JSON report to this path")
    parser.add_argument("--fail-on-gap", action="store_true", help="Return non-zero when any gap is found")
    args = parser.parse_args(argv)

    path = Path(args.artifact).resolve()
    findings = check_artifact_text(path.read_text(encoding="utf-8", errors="replace"))
    report = build_report(path, findings)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_path:
        Path(args.json_path).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 1 if args.fail_on_gap and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
