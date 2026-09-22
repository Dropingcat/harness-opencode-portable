#!/usr/bin/env python3
"""justification_check.py — Волна 4, детерм. проверка обоснованности.

Вердикт без justification/reason/evidence/rationale → OPEN (не принимается).
Также проверяет, что OPEN-вердикты имеют аларм (для воспроизводимости).

Usage: python3 justification_check.py <verdicts_processed.json> <rules.yaml> <out.json> [--report <alarms.json>]
"""
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path


def load_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_verdicts(verdicts, rules):
    jr = rules.get("justification_required", {})
    enabled = jr.get("enabled", True)
    fields = jr.get("fields", ["justification", "reason", "evidence", "rationale"])
    fallback = jr.get("fallback_status", "OPEN")
    open_reason = jr.get("open_reason", "verdict_without_justification")

    alarms = []
    n_open_new = 0
    for grp in verdicts:
        verdict = grp.get("verdict", "")
        justification = grp.get("justification", "")
        has_just = any(grp.get(f) for f in fields)
        original = grp.get("_original_verdict", "")

        # 1) вердикт без обоснования → OPEN
        if enabled and not has_just:
            grp["_justification_status"] = "missing"
            if verdict not in ("OPEN",):
                grp["_original_verdict"] = verdict
                grp["verdict"] = fallback
                grp["_verdict_changed_by"] = open_reason
                grp["_alarm"] = {"type": open_reason,
                                 "group": grp.get("original_index"),
                                 "detail": "вердикт без justification/reason/evidence"}
                alarms.append(grp["_alarm"])
                n_open_new += 1
        else:
            grp["_justification_status"] = "present"

        # 2) OPEN без аларма → добавить аларм
        if grp.get("verdict") == "OPEN" and "_alarm" not in grp:
            grp["_alarm"] = {"type": "open_without_alarm",
                             "group": grp.get("original_index"),
                             "detail": "OPEN-статус без аларма эскалации"}
            alarms.append(grp["_alarm"])

    return {"n_verdicts": len(verdicts),
            "n_open_new": n_open_new,
            "n_open_total": sum(1 for g in verdicts if g.get("verdict") == "OPEN"),
            "n_alarms": len(alarms)}


def main():
    if len(sys.argv) not in (4, 6):
        print("Usage: python3 justification_check.py <verdicts.json> <rules.yaml> <out.json> [--report <alarms.json>]",
              file=sys.stderr)
        sys.exit(1)
    verdicts_path, rules_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    report_path = None
    if len(sys.argv) == 6 and sys.argv[4] == "--report":
        report_path = sys.argv[5]

    verdicts = json.load(open(verdicts_path, encoding="utf-8"))
    if isinstance(verdicts, dict) and "verdicts" in verdicts:
        verdicts = verdicts["verdicts"]
    rules = load_yaml(rules_path)

    summary = check_verdicts(verdicts, rules)

    # out.json всегда пишем (run_step проверяет артефакт)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"verdicts": verdicts, "summary": summary}, f,
                  ensure_ascii=False, indent=1)

    # алармы — отдельный отчёт (для synthesizer)
    if report_path:
        alarms = [g for g in verdicts if "_alarm" in g]
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({"alarms": alarms, "summary": summary}, f,
                      ensure_ascii=False, indent=1)

    print(f"✅ justification_check: вердиктов {summary['n_verdicts']}, "
          f"новых OPEN {summary['n_open_new']}, OPEN всего {summary['n_open_total']}, "
          f"алармов {summary['n_alarms']}")


if __name__ == "__main__":
    main()
