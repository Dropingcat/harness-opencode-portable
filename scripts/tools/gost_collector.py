#!/usr/bin/env python3
"""gost_collector.py — сбор нормативных документов (ГОСТ/ТУ) для марок.

Закрывает TD-122/123/124/125: маппинг материал→норматив, скачивание PDF
с провенансом (URL, дата, sha256, статус), реестр собранного.

Маппинг (из material_cards, F:\\1\\_STRUCTURED\\07_AUTOREF):
  Тех.железо → ГОСТ 11036-75 / 3836-83
  Р18       → ГОСТ 19265-73
  Р6М5      → ГОСТ 19265-73
  ВКС-10    → ТУ 14-1-4999-91 (пробел!), ГОСТ 4543-71
  08Х18Н10Т → ГОСТ 5632-2014

Usage:
  python gost_collector.py registry                 # показать маппинг и статус
  python gost_collector.py collect --mark ВКС-10    # скачать недостающие для марки
  python gost_collector.py collect --all            # скачать всё недостающее
  python gost_collector.py provenance --gost 5632-2014  # показать провенанс

Env: GOST_OUT_DIR (папка ГОСТы_ТУ), GOST_COLLECTOR_DRY.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_OUT = os.environ.get("GOST_OUT_DIR", r"F:\1\_STRUCTURED\09_LITERATURE\1_Литература_данные\ГОСТы_ТУ")
HERE = Path(__file__).resolve().parent
DOWNLOADER = HERE / "downloader.py"

# TD-123: маппинг материал → [нормативы] (номер, название, источник)
MAPPING = {
    "Тех.железо": [
        {"gost": "11036-75", "title": "Прутки из технического железа", "src": "material_card_01"},
        {"gost": "3836-83", "title": "Железо техническое", "src": "material_card_01"},
    ],
    "Р18": [
        {"gost": "19265-73", "title": "Прутки из быстрорежущей стали", "src": "material_card_02"},
    ],
    "Р6М5": [
        {"gost": "19265-73", "title": "Прутки из быстрорежущей стали", "src": "material_card_03"},
    ],
    "ВКС-10": [
        {"gost": "4543-71", "title": "Прокат из легированных сталей", "src": "material_card_04"},
        {"gost": "TU-14-1-4999-91", "title": "ТУ 14-1-4999-91 ВКС-10 (металлопродукция)", "src": "material_card_04", "url": "https://www.splav-kharkov.com/gost/"},
    ],
    "08Х18Н10Т": [
        {"gost": "5632-2014", "title": "Стали нержавеющие коррозионностойкие", "src": "material_card_05"},
    ],
}

# Реальные URL (splav-kharkov) для ГОСТов, где известны (TD-125)
KNOWN_URLS = {
    "19265-73": "https://www.splav-kharkov.com/gost/54.pdf",
    "11036-75": "https://www.splav-kharkov.com/gost/307.pdf",
    "4543-71": "https://www.splav-kharkov.com/gost/96.pdf",
    "3836-83": "https://www.splav-kharkov.com/gost/300.pdf",
    "5632-2014": "https://www.splav-kharkov.com/gost/182_n.pdf",
    "5632-72": "https://www.splav-kharkov.com/gost/182.pdf",
}


def _provenance_file(out: Path, gost: str) -> Path:
    return out / f"{gost}.prov.json"


def _load_provenance(out: Path, gost: str) -> dict | None:
    p = _provenance_file(out, gost)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _registry(out: Path) -> list:
    rows = []
    for mark, norms in MAPPING.items():
        for n in norms:
            g = n["gost"]
            prov = _load_provenance(out, g)
            pdf = _pdf_path(out, g)
            if prov:
                status = "downloaded"
            elif pdf.exists():
                status = "downloaded_no_prov"
            else:
                status = "missing"
            rows.append({
                "mark": mark, "gost": g, "title": n["title"],
                "status": status, "prov": prov,
            })
    return rows


def _pdf_path(out: Path, gost: str) -> Path:
    # известные имена из существующего набора: GOST_<gost>__<file>.pdf или GOST_<gost>.pdf
    candidates = [out / f"GOST_{gost}.pdf", out / f"GOST_{gost}__"]
    for c in candidates:
        if c.is_file():
            return c
    # поиск по префиксу
    for f in out.glob(f"GOST_{gost}*"):
        if f.is_file():
            return f
    return out / f"GOST_{gost}.pdf"


def cmd_registry(args) -> int:
    out = Path(args.out)
    rows = _registry(out)
    print(f"{'МАРКА':14s} {'ГОСТ/ТУ':16s} {'Статус':18s} Название")
    print("-" * 88)
    missing = 0
    no_prov = 0
    for r in rows:
        if r["status"] == "missing":
            mark = "MISSING"
            missing += 1
        elif r["status"] == "downloaded_no_prov":
            mark = "PDF, NO PROV"
            no_prov += 1
        else:
            mark = "OK"
        print(f"{r['mark']:14s} {r['gost']:16s} {mark:18s} {r['title'][:40]}")
    print(f"\nИтого: {len(rows)} записей, недостающих: {missing}, без провенанса: {no_prov}")
    return 0


def cmd_backfill(args) -> int:
    """Сгенерировать провенанс для уже скачанных PDF (TD-124)."""
    out = Path(args.out)
    made = 0
    for f in out.glob("GOST_*.pdf"):
        gost = re.match(r"GOST_([^_]+)", f.name)
        if not gost:
            continue
        g = gost.group(1)
        if _load_provenance(out, g):
            continue
        data = f.read_bytes()
        prov = {
            "file": f.name,
            "source_url": "backfill: ручная загрузка (URL неизвестен)",
            "download_date": datetime.date.today().isoformat(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "method": "backfill",
            "verification_status": "unknown_source",
            "gost": g,
        }
        _provenance_file(out, g).write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
        made += 1
        print(f"  backfill: {f.name} -> {g}.prov.json")
    print(f"Провенанс создан для {made} PDF")
    return 0


def _download_gost(gost: str, url: str, out: Path, dry: bool) -> int:
    """Скачивание через downloader.py url (провенанс генерируется там)."""
    name = f"GOST_{gost}.pdf"
    target = out / name
    if target.exists() and _load_provenance(out, gost):
        print(f"  {gost}: уже скачан ({target})")
        return 0
    if dry:
        print(f"  DRY: {gost} <- {url}")
        return 0
    py = sys.executable
    if not Path(py).exists():
        py = "python"
    r = subprocess.run(
        [py, str(DOWNLOADER), "url", "--url", url, "--out", str(out), "--name", name, "--expect", "pdf"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if r.returncode != 0:
        print(f"  {gost}: FAIL {r.stdout.strip()[-150:]} {r.stderr.strip()[-100:]}")
        return r.returncode
    print(f"  {gost}: OK")
    return 0


def cmd_collect(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dry = os.environ.get("GOST_COLLECTOR_DRY") == "1" or args.dry
    marks = [args.mark] if args.mark else (list(MAPPING) if args.all else [])
    if not marks:
        print("Укажи --mark <марка> или --all", file=sys.stderr)
        return 2
    code = 0
    for mark in marks:
        norms = MAPPING.get(mark)
        if not norms:
            print(f"Марка {mark} не в маппинге. Доступно: {list(MAPPING)}", file=sys.stderr)
            code = 2
            continue
        print(f"\n=== {mark} ===")
        for n in norms:
            g = n["gost"]
            url = n.get("url") or KNOWN_URLS.get(g) or n.get("gost_url")
            if not url:
                print(f"  {g}: НЕТ URL (нужно найти источник) — TD-122")
                code = 3
                continue
            rc = _download_gost(g, url, out, dry)
            if rc != 0:
                code = rc
    return code


def cmd_provenance(args) -> int:
    out = Path(args.out)
    prov = _load_provenance(out, args.gost)
    if not prov:
        print(f"Нет провенанса для {args.gost} в {out}", file=sys.stderr)
        return 1
    print(json.dumps(prov, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Сбор ГОСТов/ТУ для марок (TD-122..125)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("registry")
    p.set_defaults(fn=cmd_registry)

    p = sub.add_parser("collect")
    p.add_argument("--mark", default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry", action="store_true")
    p.set_defaults(fn=cmd_collect)

    p = sub.add_parser("provenance")
    p.add_argument("--gost", required=True)
    p.set_defaults(fn=cmd_provenance)

    p = sub.add_parser("backfill", help="сгенерировать провенанс для скачанных PDF")
    p.set_defaults(fn=cmd_backfill)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())