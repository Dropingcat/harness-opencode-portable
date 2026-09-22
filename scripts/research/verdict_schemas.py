"""Pydantic-схемы для вердиктов верификатора (exp1)."""

import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SourceModel(BaseModel):
    title: str
    type: str
    trust: float = Field(ge=0.0, le=1.0)
    excerpt: str = ""
    cited: int | None = None


class CaveatModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    severity: str | None = None
    text: str = ""


class NumericModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: dict = {}
    status: str | None = None
    details: str = ""


class VerdictModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    claim_id: int
    claim_text: str
    verdict: Literal["SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS",
                     "OPEN", "GAP-UNVERIFIED"]
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[SourceModel] = []
    caveats: list[CaveatModel] = []
    reason: str = ""
    numeric_comparison: dict | None = None
    post_processed: bool = Field(default=False, alias="_post_processed")
    changes: list = Field(default_factory=list, alias="_changes")
    caveats_total: int = Field(default=0, alias="_caveats_total")
    caveats_critical: int = Field(default=0, alias="_caveats_critical")


def validate_verdicts(data: list[dict]) -> list[str]:
    errors: list[str] = []
    for i, item in enumerate(data):
        try:
            VerdictModel.model_validate(item)
        except ValidationError as exc:
            errors.append(f"Item {i}: {exc}")
    return errors


def main() -> None:
    """CLI-предвалидация вердиктов (WARNING, не блокирует).

    Usage:
        python3 verdict_schemas.py <verdicts.json>
    """
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 verdict_schemas.py <verdicts.json>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"ОШИБКА: не удалось прочитать {path}: {exc}", file=sys.stderr)
        sys.exit(2)

    if isinstance(data, dict):
        data = data.get("verdicts", [data])
    if not isinstance(data, list):
        data = [data]

    errors = validate_verdicts(data)
    for err in errors:
        print(f"⚠️ WARNING: {err}", file=sys.stderr)
    print(f"✅ verdict_schemas: {len(data)} вердиктов, нарушений схемы: {len(errors)}")
    sys.exit(0)


if __name__ == "__main__":
    main()