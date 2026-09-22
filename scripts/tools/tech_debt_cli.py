#!/usr/bin/env python3
"""tech_debt_cli.py — канонический CLI для управления реестром техдолгов.

Заменяет десятки ad-hoc скриптов (add_td*.py, close_td*.py, update_td*.py),
которые агенты плодили в C:\\Temp\\opencode. Единая точка правки
config/tech_debt.json + регенерация docs/TRACKERS/TECH_DEBT_MASTER.md.

Usage:
    python tech_debt_cli.py add   --id TD-XXX [--owner code-orchestrator] [--severity high] \\
                                  --title "..." [--notes "..."] [--acceptance "..."]
    python tech_debt_cli.py close --id TD-XXX [--progress "..."]
    python tech_debt_cli.py update --id TD-XXX [--title "..."] [--severity ...] [--notes ...] [--progress ...]
    python tech_debt_cli.py get   --id TD-XXX            # показать запись (без секретов)
    python tech_debt_cli.py list  [--owner research-orchestrator] [--status open] [--severity high]
    python tech_debt_cli.py next  [--owner code-orchestrator]    # следующий свободный ID (TD-XXX+1)
    python tech_debt_cli.py master [--root <harness-root>]       # перегенерировать TECH_DEBT_MASTER.md

Поля записи (схема, как в существующих): id, owner, presentation_category,
sunset_at, title, status_detail, kind, status, severity, acceptance, area,
source_status, notes, progress.
"""
from __future__ import annotations

import argparse
import datetime
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

HERE = Path(__file__).resolve().parent          # scripts/tools
HARNESS_ROOT = HERE.parent.parent               # scripts/tools/../.. = harness root
# Канонический реестр — portable (GitHub-версия). Work — зеркало через sync_tech_debt.py.
DEFAULT_DEBT = Path(os.environ.get("TECH_DEBT_PATH", r"E:\opencode_harness_portable\config\tech_debt.json"))
DEFAULT_MASTER = HARNESS_ROOT / "docs" / "TRACKERS" / "TECH_DEBT_MASTER.md"
DEFAULT_GEN = HARNESS_ROOT / "scripts" / "glossary" / "coder_techdebt_master.py"

VALID_SEVERITY = ("critical", "high", "medium", "low")
VALID_STATUS = ("open", "closed")


def _load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(path, data: dict) -> None:
    path = Path(path)
    open_c = sum(1 for r in data["debts"] if r.get("status") == "open")
    closed_c = sum(1 for r in data["debts"] if r.get("status") == "closed")
    data["counts"] = {"total": len(data["debts"]), "open": open_c, "closed": closed_c}
    data["updated"] = datetime.date.today().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _next_id(debts: list[dict]) -> str:
    nums = [int(re.sub(r"\D", "", r["id"])) for r in debts if re.match(r"^TD-\d+", r["id"])]
    return f"TD-{max(nums) + 1}" if nums else "TD-001"


def _find(debts: list[dict], id_: str) -> dict | None:
    return next((r for r in debts if r["id"] == id_), None)


def cmd_add(args) -> int:
    data = _load(args.debt)
    if _find(data["debts"], args.id):
        print(f"ERROR: {args.id} уже существует (use update)", file=sys.stderr)
        return 1
    if not args.title:
        print("ERROR: --title обязателен", file=sys.stderr)
        return 1
    record = {
        "id": args.id,
        "owner": args.owner or "code-orchestrator",
        "presentation_category": "ACTIVE",
        "sunset_at": args.sunset_at or (datetime.date.today().replace(year=datetime.date.today().year + 1).isoformat()),
        "title": args.title,
        "status_detail": "OPEN_CURRENT",
        "kind": args.kind or "tooling",
        "status": "open",
        "severity": args.severity or "medium",
        "acceptance": args.acceptance or "",
        "area": args.area or "",
        "source_status": "open",
        "notes": args.notes or "",
        "progress": args.progress or f"{datetime.date.today().isoformat()}: создано через tech_debt_cli.py",
    }
    data["debts"].append(record)
    _save(args.debt, data)
    print(f"OK: {args.id} добавлен (total={len(data['debts'])})")
    return 0


def cmd_close(args) -> int:
    data = _load(args.debt)
    r = _find(data["debts"], args.id)
    if not r:
        print(f"ERROR: {args.id} не найден", file=sys.stderr)
        return 1
    r["status"] = "closed"
    r["status_detail"] = "CLOSED"
    r["presentation_category"] = "RESOLVED"
    if args.progress:
        r["progress"] = args.progress
    _save(args.debt, data)
    print(f"OK: {args.id} закрыт")
    return 0


def cmd_update(args) -> int:
    data = _load(args.debt)
    r = _find(data["debts"], args.id)
    if not r:
        print(f"ERROR: {args.id} не найден", file=sys.stderr)
        return 1
    for field in ("title", "owner", "severity", "kind", "acceptance", "area", "notes", "progress", "source_status", "status_detail", "sunset_at", "presentation_category"):
        val = getattr(args, field, None)
        if val is not None:
            r[field] = val
    if args.status:
        r["status"] = args.status
        if args.status == "closed":
            r["status_detail"] = "CLOSED"
            r["presentation_category"] = "RESOLVED"
    _save(args.debt, data)
    print(f"OK: {args.id} обновлён")
    return 0


def cmd_get(args) -> int:
    data = _load(args.debt)
    r = _find(data["debts"], args.id)
    if not r:
        print(f"ERROR: {args.id} не найден", file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args) -> int:
    data = _load(args.debt)
    rows = data["debts"]
    if args.owner:
        rows = [r for r in rows if r.get("owner") == args.owner]
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if args.severity:
        rows = [r for r in rows if r.get("severity") == args.severity]
    rows.sort(key=lambda r: r["id"])
    for r in rows:
        print(f"{r['id']:8s} [{r.get('severity','?'):8s}] {r.get('owner','?'):24s} {(r['title'] or '')[:80]}")
    print(f"-- total: {len(rows)}")
    return 0


def cmd_next(args) -> int:
    data = _load(args.debt)
    print(_next_id(data["debts"]))
    return 0


# --- TD-144: авто-оформление долга по описанию (эвристика + опц. LLM-диспатч) ---
AUTO_HINTS = [
    # (regex, kind, severity, owner)
    (r"(поиск|источник|литератур|статья|верификац|клайм|гост|норматив)", "research", "high", "research-orchestrator"),
    (r"(роутер|роут|маршрут|route|диспатч|bundle|snapshot)", "routing", "high", "code-orchestrator"),
    (r"(python|скрипт|инструмент|tools|powershell|кавычк|окружени|venv|chromadb)", "tooling", "medium", "code-orchestrator"),
    (r"(архитектур|контракт|провайдер|хардкод|мёртв|конфиг)", "architecture", "high", "code-orchestrator"),
    (r"(таймаут|сеть|dns|timeout|медленн)", "robustness", "high", "research-orchestrator"),
    (r"(база|данных|db|реестр|json)", "data-quality", "medium", "research-orchestrator"),
    (r"(процесс|ритуал|цикл|перфекцион|повтор)", "process", "medium", "research-orchestrator"),
]


def _auto_generate(desc: str) -> dict:
    """Детерминированная эвристика: kind/severity/owner по ключевым словам."""
    low = desc.lower()
    kind, sev, owner = "tooling", "medium", "code-orchestrator"
    for pat, k, s, o in AUTO_HINTS:
        import re
        if re.search(pat, low):
            kind, sev, owner = k, s, o
            break
    # заголовок: первые ~110 символов описания (первое предложение)
    title = re.split(r"[.!?\n]", desc)[0].strip()
    if len(title) > 110:
        title = title[:107] + "..."
    if not title:
        title = desc[:110]
    return {"kind": kind, "severity": sev, "owner": owner, "title": title}


def _tokens(s: str) -> set:
    """Стоп-слова + токенизация (лат/кир, >=4 символа)."""
    import re
    stop = {"этот", "который", "которая", "через", "потому", "блок", "вместо", "сказать",
            "which", "that", "with", "from", "then", "себя", "между", "после", "когда"}
    toks = set(re.findall(r"[a-zа-яё]{4,}", s.lower()))
    return toks - stop


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    # Jaccard взвешенный: важнее общие значимые слова, а не размер
    return inter / (len(ta) + len(tb) - inter) if (len(ta) + len(tb) - inter) else 0.0


def _find_similar(debts: list, desc: str, threshold: float = 0.35) -> dict | None:
    """Найти похожий долг (TD-147 дедуп).

    Сравниваем только по TITLE (короткий, не раздувает знаменатель).
    Критерий: >=2 общих значимых токена И доля общих в минимуме двух наборов
    (>= threshold). Ищем в ОТКРЫТЫХ записях. Если похожий найден среди закрытых
    с маркером «ДУБЛИКАТ»/«РЕШЕНО» — не считаем дублем (долг реально решён).
    """
    desc_toks = _tokens(desc)
    best = None
    best_score = 0.0
    for r in debts:
        if r.get("status") != "open":
            continue
        title = r.get("title") or ""
        title_toks = _tokens(title)
        common = desc_toks & title_toks
        if len(common) < 2:
            continue
        # доля общих значимых в меньшем наборе — «описание в основном про это»
        overlap_ratio = len(common) / min(len(desc_toks), len(title_toks))
        if overlap_ratio >= threshold and overlap_ratio > best_score:
            best_score = overlap_ratio
            best = r
    return best


def _similarity_score(debts: list, desc: str, threshold: float = 0.35) -> float:
    """Скор лучшего похожего открытого долга (для вывода)."""
    best = _find_similar(debts, desc, threshold)
    if not best:
        return 0.0
    desc_toks = _tokens(desc)
    title_toks = _tokens(best.get("title") or "")
    common = desc_toks & title_toks
    return len(common) / min(len(desc_toks), len(title_toks)) if title_toks else 0.0


def _find_similar_closed(debts: list, desc: str, threshold: float = 0.35) -> dict | None:
    """Похожий ЗАКРЫТЫЙ долг — предупреждение о возможной регрессии."""
    desc_toks = _tokens(desc)
    best = None
    best_score = threshold
    for r in debts:
        if r.get("status") != "closed":
            continue
        title = r.get("title") or ""
        title_toks = _tokens(title)
        common = desc_toks & title_toks
        if len(common) < 2:
            continue
        overlap_ratio = len(common) / min(len(desc_toks), len(title_toks))
        if overlap_ratio >= best_score:
            best_score = overlap_ratio
            best = r
    return best


def cmd_add_auto(args) -> int:
    """add --auto '<описание>' — оформить долг по описанию.

    Эвристика задаёт kind/severity/owner; при --llm опционально вызывается
    LLM-диспатч (claim-parser-runner) для структуризации notes/acceptance.
    TD-147: дедуп-гейт — если похожий открытый долг уже есть, предложить update.
    """
    if not args.desc:
        print("ERROR: --auto требует описание ('<текст>')", file=sys.stderr)
        return 1
    data = _load(args.debt)
    # TD-147: дедуп-гейт
    dup = _find_similar(data["debts"], args.desc, threshold=args.dup_threshold)
    if dup is not None and not args.force:
        print(f"WARN: похожий долг уже есть — {dup['id']}: {(dup.get('title') or '')[:80]}")
        print(f"  Похожесть: {_similarity_score(data['debts'], args.desc, args.dup_threshold):.2f}")
        print(f"  Хочешь создать дубликат? Используй --force, ИЛИ обнови существующий:")
        print(f"    python tech_debt_cli.py update --id {dup['id']} --notes '<дополнение>' --progress '...'")
        return 3
    # TD-147: предупреждение о похожих ЗАКРЫТЫХ (вероятно регрессия) -> блокировка без --force
    closed_dup = _find_similar_closed(data["debts"], args.desc, threshold=args.dup_threshold)
    if closed_dup and not args.force:
        print(f"WARN: похожий долг {closed_dup['id']} уже ЗАКРЫТ ({closed_dup.get('status_detail')}) — это может быть РЕГРЕССИЯ той же проблемы, а НЕ новый долг.")
        print(f"  Проверь: python tech_debt_cli.py get --id {closed_dup['id']}")
        print(f"  Если это новая проблема — создай как дубликат: --force. Если та же — реанимируй: update --id {closed_dup['id']} --status open --progress 'регрессия'")
        return 3
    nid = args.id or _next_id(data["debts"])
    if _find(data["debts"], nid):
        print(f"ERROR: {nid} уже существует", file=sys.stderr)
        return 1

    gen = _auto_generate(args.desc)
    notes = args.desc
    acceptance = ""
    if args.llm:
        # LLM-диспатч через claim-parser-runner (TD-144)
        opencode_bin = os.environ.get("OPENCODE_BIN", "opencode")
        prompt = (f"Оформи техдолг по описанию. Верни JSON: "
                  f"{{title, notes(2-4 предложения, зачем/что), acceptance(критерий готовности), "
                  f"severity(critical|high|medium|low), owner}}. Описание: {args.desc}")
        try:
            r = subprocess.run([opencode_bin, "run", "--agent", "claim-parser-runner", prompt],
                               capture_output=True, text=True, timeout=300,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                               encoding="utf-8", errors="replace")
            if r.returncode == 0 and r.stdout.strip():
                # извлечь JSON из ответа
                import re as _re
                m = _re.search(r"\{.*\}", r.stdout, _re.DOTALL)
                if m:
                    import json as _json
                    parsed = _json.loads(m.group(0))
                    gen["title"] = parsed.get("title", gen["title"])
                    notes = parsed.get("notes", notes)
                    acceptance = parsed.get("acceptance", "")
                    if parsed.get("severity") in VALID_SEVERITY:
                        gen["severity"] = parsed["severity"]
                    if parsed.get("owner"):
                        gen["owner"] = parsed["owner"]
        except Exception as e:
            print(f"LLM-диспатч не сработал ({e}), используется эвристика", file=sys.stderr)

    record = {
        "id": nid,
        "owner": args.owner or gen["owner"],
        "presentation_category": "ACTIVE",
        "sunset_at": args.sunset_at or (datetime.date.today().replace(year=datetime.date.today().year + 1).isoformat()),
        "title": args.title or gen["title"],
        "status_detail": "OPEN_CURRENT",
        "kind": args.kind or gen["kind"],
        "status": "open",
        "severity": args.severity or gen["severity"],
        "acceptance": args.acceptance or acceptance,
        "area": args.area or "",
        "source_status": "open",
        "notes": notes,
        "progress": f"{datetime.date.today().isoformat()}: авто-фиксация через tech_debt_cli.py add --auto",
    }
    data["debts"].append(record)
    _save(args.debt, data)
    print(f"OK: {nid} авто-добавлен (total={len(data['debts'])})")
    print(f"  kind={record['kind']} severity={record['severity']} owner={record['owner']}")
    print(f"  title: {record['title'][:100]}")
    return 0


def cmd_master(args) -> int:
    root = Path(args.root) if args.root else HARNESS_ROOT
    gen = root / "scripts" / "glossary" / "coder_techdebt_master.py"
    if not gen.exists():
        print(f"ERROR: генератор не найден: {gen}", file=sys.stderr)
        return 1
    r = subprocess.run([sys.executable, str(gen), "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout, file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        return r.returncode
    print(r.stdout.strip())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Канонический CLI техдолгов")
    ap.add_argument("--debt", default=str(DEFAULT_DEBT), help="путь к tech_debt.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="добавить долг")
    p.add_argument("--id", required=True)
    p.add_argument("--owner", default=None)
    p.add_argument("--severity", choices=VALID_SEVERITY, default="medium")
    p.add_argument("--kind", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--notes", default=None)
    p.add_argument("--acceptance", default=None)
    p.add_argument("--area", default=None)
    p.add_argument("--progress", default=None)
    p.add_argument("--sunset-at", dest="sunset_at", default=None)
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("auto", help="авто-оформить долг по описанию (TD-144)")
    p.add_argument("--id", default=None)
    p.add_argument("--desc", required=True, help="описание блока (текстом)")
    p.add_argument("--owner", default=None)
    p.add_argument("--severity", choices=VALID_SEVERITY, default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--acceptance", default=None)
    p.add_argument("--area", default=None)
    p.add_argument("--llm", action="store_true", help="LLM-диспатч для оформления")
    p.add_argument("--dup-threshold", type=float, default=0.35, help="порог похожести для дедуп-гейта (TD-147)")
    p.add_argument("--force", action="store_true", help="создать дубликат, игнорируя дедуп-гейт")
    p.add_argument("--sunset-at", dest="sunset_at", default=None)
    p.set_defaults(fn=cmd_add_auto)

    p = sub.add_parser("close", help="закрыть долг")
    p.add_argument("--id", required=True)
    p.add_argument("--progress", default=None)
    p.set_defaults(fn=cmd_close)

    p = sub.add_parser("update", help="обновить долг")
    p.add_argument("--id", required=True)
    p.add_argument("--title", default=None)
    p.add_argument("--owner", default=None)
    p.add_argument("--severity", choices=VALID_SEVERITY, default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--status", choices=VALID_STATUS, default=None)
    p.add_argument("--notes", default=None)
    p.add_argument("--acceptance", default=None)
    p.add_argument("--area", default=None)
    p.add_argument("--progress", default=None)
    p.add_argument("--source-status", dest="source_status", default=None)
    p.add_argument("--status-detail", dest="status_detail", default=None)
    p.add_argument("--sunset-at", dest="sunset_at", default=None)
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("get", help="показать долг")
    p.add_argument("--id", required=True)
    p.set_defaults(fn=cmd_get)

    p = sub.add_parser("list", help="список долгов")
    p.add_argument("--owner", default=None)
    p.add_argument("--status", choices=VALID_STATUS, default=None)
    p.add_argument("--severity", choices=VALID_SEVERITY, default=None)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("next", help="следующий свободный ID")
    p.set_defaults(fn=cmd_next)

    p = sub.add_parser("master", help="перегенерировать TECH_DEBT_MASTER.md")
    p.add_argument("--root", default=None)
    p.set_defaults(fn=cmd_master)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())