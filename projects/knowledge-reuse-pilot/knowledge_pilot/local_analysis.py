"""Deterministic local table profiling; no LLM, network or corpus mutation."""
from pathlib import Path
import csv
import math

from .catalog import digest_file


def table_profile(path, max_rows=100000):
    path = Path(path)
    if path.suffix.lower() not in {".csv", ".tsv"}:
        raise ValueError("table_profile supports CSV/TSV only")
    before = digest_file(path)
    max_rows = max(1, min(int(max_rows), 100000))
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        sample = stream.read(8192)
        stream.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
        reader = csv.DictReader(stream, dialect=dialect)
        headers = (reader.fieldnames or [])[:64]
        numeric = {name: {"count": 0, "sum": 0.0, "min": None, "max": None} for name in headers}
        rows, truncated = 0, False
        for row in reader:
            if rows >= max_rows:
                truncated = True
                break
            rows += 1
            for name in headers:
                try:
                    value = float(str(row.get(name, "")).strip().replace(",", "."))
                except ValueError:
                    continue
                if not math.isfinite(value):
                    continue
                item = numeric[name]
                item["count"] += 1
                item["sum"] += value
                item["min"] = value if item["min"] is None else min(item["min"], value)
                item["max"] = value if item["max"] is None else max(item["max"], value)
    if digest_file(path) != before:
        raise ValueError("table changed during profiling; result is not reusable")
    for item in numeric.values():
        item["mean"] = item.pop("sum") / item["count"] if item["count"] else None
    return {"method": "csv-profile/1", "path": str(path.resolve()), "sha256": before,
            "rows_profiled": rows, "truncated": truncated, "numeric": numeric,
            "headers_truncated": len(reader.fieldnames or []) > 64,
            "note": "descriptive parsing only; units and scientific validity are not assessed"}
