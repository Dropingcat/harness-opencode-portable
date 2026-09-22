#!/usr/bin/env python3
"""synthesizer.py — генерация финального отчёта (Node 3, пилот).

Формирует Markdown-отчёт из verdicts.json через промпт к deepseek-v4-flash.

Usage:
    python3 synthesizer.py <verdicts.json> <final_report.md>
    python3 synthesizer.py <verdicts.json> <tribunal.json> <final_report.md>

Вход: verdicts.json может быть
    - list  плоских вердиктов (exp1): [{claim_id, claim_text, verdict, ...}]
    - dict  {verdicts: [...], statistics: {...}}

P1-фикс: опциональный tribunal.json — источник истины финальных вердиктов.
  Финальные вердикты = verdicts_processed, перекрытые вердиктами трибунала по
  claim_id/original_index (трибунал имеет приоритет). Отчёт не может содержать
  вердикт, опровергнутый трибуналом.
Статистика (statistics) опциональна: если её нет, подсчитывается по вердиктам.
"""
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import os
from pathlib import Path

EMOJI = {"SUPPORTED": "🟢", "CONTRADICTED": "🔴", "UNSUPPORTED": "🟡", "AMBIGUOUS": "🟠"}

STAT_KEYS = ("supported", "contradicted", "unsupported", "ambiguous")


def load_verdicts(data):
    """Вердикты из list-артефакта (exp1) или dict {verdicts: [...]}."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        verdicts = data.get("verdicts", [])
        if verdicts is None:
            return []
        return verdicts if isinstance(verdicts, list) else [verdicts]
    return []


def load_stats(data):
    """Статистика из dict-артефакта ({} для list)."""
    if isinstance(data, dict):
        stats = data.get("statistics")
        return stats if isinstance(stats, dict) else {}
    return {}


def compute_stats(verdicts, stats=None):
    """Дополняет stats недостающими счётчиками по вердиктам (fallback)."""
    merged = {}
    for k in STAT_KEYS:
        merged[k] = (stats or {}).get(k, 0)
    counts = {k: 0 for k in STAT_KEYS}
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        key = str(v.get("verdict", "")).upper()
        if key in EMOJI:
            counts[key.lower()] += 1
    for k in STAT_KEYS:
        if (stats or {}).get(k) is None and merged[k] == 0:
            merged[k] = counts[k]
    merged["total"] = (stats or {}).get("total", len(verdicts))
    return merged


def generate_recommendations(stats, verdicts):
    """LLM-генерация рекомендаций и вопросов (опционально)."""
    from openai import OpenAI
    api_key = os.environ.get("AITUNNEL_KEY") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AITUNNEL_KEY/OPENAI_API_KEY не задан")
    client = OpenAI(api_key=api_key, base_url="https://api.aitunnel.ru/v1")
    prompt = (
        "Ты — физик-эксперт (ФКС: азотирование, РФА, дифракция). "
        "На основе вердиктов верификации сформируй:\n"
        "1. 3-5 рекомендаций автору по улучшению текста\n"
        "2. 2-3 конкретных вопроса автору ('почему так', 'где исходные данные')\n\n"
        f"Статистика: {stats}\n"
        f"Вердикты (первые 5): {json.dumps(verdicts[:5], ensure_ascii=False)}\n\n"
        "Ответ в Markdown. Кратко, по делу."
    )
    resp = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2000,
        timeout=120,
    )
    return resp.choices[0].message.content.strip()


def build_report(verdicts, stats):
    """Формирует Markdown-отчёт (без LLM-секции)."""
    lines = [
        "# Отчёт верификации (пилот science-auditor)",
        "",
        "## Сводка",
        f"- Всего claims: **{stats.get('total', len(verdicts))}**",
        f"- {EMOJI.get('SUPPORTED', '🟢')} Подтверждено: **{stats.get('supported', 0)}**",
        f"- {EMOJI.get('CONTRADICTED', '🔴')} Опровергнуто: **{stats.get('contradicted', 0)}**",
        f"- {EMOJI.get('UNSUPPORTED', '🟡')} Требует проверки: **{stats.get('unsupported', 0)}**",
        f"- {EMOJI.get('AMBIGUOUS', '🟠')} Противоречиво: **{stats.get('ambiguous', 0)}**",
        "",
        "## Детали по claims",
        "",
    ]
    for i, v in enumerate(verdicts, 1):
        if not isinstance(v, dict):
            continue
        cid = v.get('claim_id', i)
        e = EMOJI.get(str(v.get("verdict", "")).upper(), "❓")
        lines.append(f"### Claim {cid}: {v.get('claim_text', '')[:80]}")
        lines.append(f"- Вердикт: {e} **{v.get('verdict', '')}** (confidence: {v.get('confidence', 0)})")
        lines.append(f"- Причина: {v.get('reason', '')}")
        lines.append("")
    return lines


def load_tribunal_groups(data):
    """Группы трибунала из tribunal.json: {groups: [...]} или list.

    Каждая группа: {claim_id, original_index, tribunal_verdict, confidence,
    justification, questions_for_author}.
    """
    if isinstance(data, dict):
        groups = data.get("groups") or []
        if isinstance(groups, list):
            return groups
        if any(k in data for k in ("tribunal_verdict", "claim_id", "original_index")):
            return [data]
        return []
    if isinstance(data, list):
        return data
    return []


def _group_key(group):
    """Ключ сопоставления группы: original_index или claim_id (строка)."""
    for key in ("original_index", "claim_id"):
        if group.get(key) is not None:
            return str(group[key])
    return None


def overlay_tribunal(verdicts, tribunal_groups):
    """Накладывает вердикты трибунала на базовые вердикты (P1).

    Трибунал — источник истины: по claim_id/original_index перекрывает
    verdict/confidence/reason базового вердикта. Группы трибунала, которых нет
    в базе, добавляются отдельно. Возвращает новый список вердиктов.
    """
    index = {}
    for tg in tribunal_groups:
        key = _group_key(tg)
        if key is not None:
            index[key] = tg

    final = []
    seen = set()
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        out = dict(v)
        key = None
        for k in ("original_index", "claim_id"):
            if v.get(k) is not None:
                key = str(v[k])
                break
        tg = index.get(key) if key is not None else None
        if tg:
            out["verdict"] = tg.get("tribunal_verdict", out.get("verdict"))
            out["confidence"] = tg.get("confidence", out.get("confidence"))
            out["reason"] = tg.get("justification") or out.get("reason", "")
            out["questions_for_author"] = tg.get("questions_for_author", [])
            out["_tribunal_overlaid"] = True
            seen.add(key)
        final.append(out)

    # группы трибунала, отсутствующие в базовых вердиктах
    for tg in tribunal_groups:
        key = _group_key(tg)
        if key is None or key in seen:
            continue
        final.append({
            "claim_id": tg.get("claim_id", tg.get("original_index")),
            "original_index": tg.get("original_index"),
            "claim_text": tg.get("claim_text", ""),
            "verdict": tg.get("tribunal_verdict", "OPEN"),
            "confidence": tg.get("confidence", 0.5),
            "reason": tg.get("justification", ""),
            "caveats": [],
            "questions_for_author": tg.get("questions_for_author", []),
            "_tribunal_overlaid": True,
        })
    return final


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 synthesizer.py <verdicts.json> [tribunal.json] <final_report.md>", file=sys.stderr)
        sys.exit(1)
    verdicts_path = sys.argv[1]
    if len(sys.argv) >= 4:
        tribunal_path, report_path = sys.argv[2], sys.argv[3]
    else:
        tribunal_path, report_path = None, sys.argv[2]
    try:
        with open(verdicts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"❌ verdicts.json не является валидным JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"❌ не удалось прочитать {verdicts_path}: {e}", file=sys.stderr)
        sys.exit(1)
    if data is None:
        print("❌ verdicts.json пуст (null) — нечего синтезировать", file=sys.stderr)
        sys.exit(1)

    verdicts = load_verdicts(data)

    # P1: трибунал как источник истины (опционально)
    if tribunal_path:
        try:
            with open(tribunal_path, "r", encoding="utf-8") as f:
                tribunal_data = json.load(f)
            tribunal_groups = load_tribunal_groups(tribunal_data)
            verdicts = overlay_tribunal(verdicts, tribunal_groups)
            n_overlaid = sum(1 for v in verdicts if v.get("_tribunal_overlaid"))
            print(f"▶ Node 3: Synthesizer — tribunal.json применён "
                  f"({len(tribunal_groups)} групп, перекрыто вердиктов: {n_overlaid})")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"⚠ tribunal.json не является валидным JSON ({e}) — "
                  f"использую verdicts без перекрытия", file=sys.stderr)
        except OSError as e:
            print(f"⚠ не удалось прочитать {tribunal_path}: {e} — "
                  f"использую verdicts без перекрытия", file=sys.stderr)

    # P1: после перекрытия трибуналом статистику считаем ПОЛНОСТЬЮ из финальных
    # вердиктов (старые счётчики из verdicts.json больше не источник истины).
    stats = compute_stats(verdicts, {} if tribunal_path else load_stats(data))
    print(f"▶ Node 3: Synthesizer ({len(verdicts)} verdicts, stats={stats})")

    lines = build_report(verdicts, stats)

    # LLM-генерация рекомендаций и вопросов (опционально)
    try:
        rec = generate_recommendations(stats, verdicts)
        lines.append("## Рекомендации и вопросы автору")
        lines.append("")
        lines.append(rec)
    except Exception as e:
        lines.append("## Рекомендации и вопросы автору")
        lines.append(f"_LLM недоступен: {e}_")

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ final_report.md: {len(lines)} строк")


if __name__ == "__main__":
    main()