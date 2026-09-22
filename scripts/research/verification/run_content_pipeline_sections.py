#!/usr/bin/env python3
"""run_content_pipeline_sections.py — сквозной прогон на кусках автореферата.

Для КАЖДОГО независимого куска (Актуальность / Научная новизна / Положения):
  текст куска → детерминированное извлечение claims → каскад (cascade_integration)
  → слой оценки (verdict_integration) → verdicts.json + sources.json + сводка.

Каждый кусок — ОТДЕЛЬНЫЙ независимый прогон (раздельный workspace).

Usage:
    python3 run_content_pipeline_sections.py <out_dir> [--no-llm]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cascade_integration as ci
import verdict_integration as vi

# независимые куски автореферата (дословно из строк автореферата_5_2в.txt)
SECTIONS = {
    "actuality": {
        "label": "Актуальность (качественный, без чисел)",
        "text": (
            "Наблюдается ускорение образования нитридных фаз при комбинированных "
            "воздействиях — лазерная обработка и вакуумное азотирование, механическая "
            "обработка и вакуумное азотирование. Структурное состояние диффузионной "
            "зоны — тип, размер, когерентность нитридов легирующих элементов и уровень "
            "микродеформаций матрицы — однозначно определяет твёрдость и износостойкость "
            "азотированного слоя. Разделение вкладов, обусловленных предварительными "
            "обработками (микродеформациями, дефектной субструктурой), в кинетику роста "
            "азотированного слоя остаётся нерешённой задачей."
        ),
    },
    "novelty": {
        "label": "Научная новизна (ЧИСЛА)",
        "text": (
            "Предварительная лазерная обработка с оплавлением поверхности (2000 Вт) "
            "индуцирует неоднородные поля микродеформаций, что увеличивает объёмную "
            "долю нитридов в сплаве ВКС-10 до 55 % (против менее 2 % при классическом "
            "азотировании). При вакуумном азотировании (540 °C, 8–24 ч) выявлены "
            "немонотонные изменения параметров решёток α-Fe, карбидов и нитридов в "
            "стали Р18 при зондировании Cu- (2–6 мкм) и Co- (6–18 мкм)."
        ),
    },
    "positions": {
        "label": "Положения (ЧИСЛА)",
        "text": (
            "В сплавах ВКС-10 и Р18 существует численная зависимость между интегральными "
            "параметрами неоднородных микродеформаций и объёмной долей формирующихся "
            "нитридных фаз. Предварительная лазерная обработка с оплавлением поверхности "
            "увеличивает объёмную долю нитридов в сплаве ВКС-10 до 55 % (по сравнению с "
            "менее 2 % при классическом азотировании). При азотировании стали Р18 "
            "(540 °C, 8–24 ч) реализуется конкуренция замещения углерода азотом."
        ),
    },
}

LAYERS = ["local_corpus", "openalex", "arxiv", "web_ddg"]


def extract_claims(text, section_name):
    from extractor_guard import deterministic_extract
    out = deterministic_extract(text, metadata=section_name)
    return out["claims"]["validated"]


def run_section(name, cfg, base_dir, use_llm):
    ws = Path(base_dir) / name
    ws.mkdir(parents=True, exist_ok=True)
    claims = extract_claims(cfg["text"], name)
    claims_path = ws / "claims.json"
    (ws / "claims.json").write_text(
        json.dumps({"status": "ok", "claims": {"validated": claims, "discarded": []}},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    sources = ci.build_sources(claims, LAYERS)
    sources_path = ws / "sources.json"
    sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    sources_map = vi.load_sources(sources_path)
    verdicts, stats = vi.build_verdicts(claims, sources_map, use_llm=use_llm)
    verdicts_path = ws / "verdicts.json"
    verdicts_path.write_text(
        json.dumps({"status": "success", "verdicts": verdicts, "statistics": stats},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "section": name, "label": cfg["label"], "ws": str(ws),
        "claims": len(claims), "stats": stats,
        "verdicts": verdicts, "sources_meta": sources["verification_meta"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir", help="базовый каталог результатов")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--section", choices=list(SECTIONS), help="только один кусок")
    args = ap.parse_args()

    use_llm = not args.no_llm
    base = Path(args.out_dir)
    base.mkdir(parents=True, exist_ok=True)

    names = [args.section] if args.section else list(SECTIONS)
    results = {}
    for name in names:
        cfg = SECTIONS[name]
        print(f"\n=== [{name}] {cfg['label']} ===")
        results[name] = run_section(name, cfg, base, use_llm)

    summary_path = base / "summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    print(f"\n✅ Прогон завершён. Артефакты: {base}")
    for name, r in results.items():
        print(f"  [{name}] claims={r['claims']} stats={r['stats']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())