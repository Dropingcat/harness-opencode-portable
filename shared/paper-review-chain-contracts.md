# Paper Review Chain Contracts — шаблоны контрактов цепочки

Источник истины для JSON-артефактов пайплайна `/review-paper`. Читать ПЕРВЫМ при диспатче любого агента цепочки рецензирования. Оркестратор передаёт нужный контракт (вход + выход + acceptance) в `prompt` субагента **целиком**, субагент не знает своего SKILL.md.

> **Принцип №0 (общий для harness'а):** LLM производит свидетельства, КОД принимает решения. Для цепочки рецензирования это означает: оркестратор **структурно валидирует** каждый возвращённый JSON (обязательные поля, типы, скоупы enum, числовые границы) и отклоняет битые артефакты на повторный диспатч. Окончательная сшивка score → вердикт идёт по детерминированным правилам (таблица в конце), а не «по ощущению».

## Модель цепочки

```
/review-paper
  │  Фаза 1
  ├─▶ paper-analyzer ─▶ analysis.json (+ figures/*.png)
  │  Фаза 1.5 (детерминированный слой)
  ├─▶ quick-assess.py ─▶ quick_assess.json   (без LLM)
  │  Фаза 2 (ПАРАЛЛЕЛЬНЫЙ fan-out, независимы)
  ├─▶ technical-reviewer   ─▶ tech_review.json
  ├─▶ reference-auditor    ─▶ reference_audit.json
  └─▶ paper-comparator     ─▶ competitor_analysis.json
  │  Фаза 3 (merge — только в контексте оркестратора, без отдельного агента)
  └─▶ сшивка scores + issues ─▶ Review_Report_<paper>.md
```

**Жёсткие имена артефактов** (в рабочей папке рецензии `${PAPER_WORKSPACE:-${OPENCODE_RUNS_DIR}/paper-review-<ts>/}`):
`analysis.json`, `quick_assess.json`, `tech_review.json`, `reference_audit.json`, `competitor_analysis.json`, `merged_scores.json`, `Review_Report_<paper>.md`.

**Порядок передачи данных:** каждый агент Фазы 2 получает входом `analysis.json` (+ `quick_assess.json` для фокусировки) и возвращает ОДИН JSON-артефакт. Ни один агент не читает чужой выход Фазы 2 — они независимы и запускаются параллельно.

---

## Контракт 1 — paper-analyzer → `analysis.json`

**Вход:** `pdf_path` (обязательно), `engine`, `output_dir` для фигур. **Инструменты:** MCP `paper-parser`, Read.

```json
{
  "status": "success | error",
  "error_message": "str (только при status=error)",
  "title": "Deep Residual Learning for Image Recognition",
  "page_count": 15,
  "language": "en | ru | zh | other",
  "char_count": 43712,
  "sections": [
    {"level": 1, "title": "Introduction"},
    {"level": 2, "title": "3.2 Bottleneck Architectures"}
  ],
  "architecture_type": "theory | experiment | application | system | mixed",
  "venue_signals": ["CVPR-style", "LLM-baselines-expected"],
  "markdown_path": "/abs/path/paper.md",
  "references": [
    {
      "index": 0,
      "authors": ["Kaiming He"], "title": "...", "venue": "CVPR", "year": "2016",
      "complete": true,
      "notes": "str | null"
    }
  ],
  "reference_stats": {"total": 42, "complete": 38, "incomplete": 4, "no_year": 2},
  "figures": [
    {"type": "figure | table | formula", "page": 3, "image_path": "/abs/figures/fig_3_1.png", "caption": "..."}
  ],
  "key_claims_preview": [
    {"text": "одно-два предложения центрального утверждения", "section": "Abstract"}
  ]
}
```

**Acceptance (детерминированно проверяет оркестратор):**
- `status` обязателен; при `error` — повторить диспатч или запросить иной способ парсинга (Read fallback).
- `title` непустой, `markdown_path` существует — иначе отклонено на повторный диспатч.
- `references` непустые при `reference_stats.total > 0`; расхождение `len(references) != reference_stats.total` → отклонено.
- `figures` путёвые при число > 0: каждый `image_path` обязан существовать.

---

## Контракт 2 — technical-reviewer → `tech_review.json`

**Вход:** `analysis.json`, `quick_assess.json`, `--venue` (если задан). **Инструменты:** MCP `academic-search` (`find_competing_methods`, `get_sota_results`, `search_related_work`), WebSearch. Зона: формулы, эксперименты, статистика, SOTA, fairness.

```json
{
  "status": "success | partial",
  "status_note": "str (при partial: чего не хватило, напр. SOTA API недоступен)",
  "dimensions": {
    "technical_correctness": {
      "score": 3.0,
      "comment": "1-2 предложения",
      "issues": [
        {
          "id": "T1", "severity": "critical | major | minor",
          "location": "Eq.5 / Section 3.2 / Table 2",
          "description": "конкретная проблема",
          "evidence": "что именно в тексте статьи подтверждает/показывает проблему",
          "recommendation": "как исправить"
        }
      ]
    },
    "experiments": {
      "score": 3.0,
      "comment": "...",
      "issues": [],
      "sota_table": [
        {"method": "...", "dataset": "...", "metric": "F1", "ours": 88.3, "sota": 90.1, "gap": -1.8, "source": "academic-search | paperswithcode | self-reported"}
      ],
      "missing_baselines": [{"name": "...", "why_important": "..."}],
      "ablation_complete": true
    },
    "statistical_rigor": {
      "score": 3.0,
      "comment": "...",
      "found": ["error bars", "multiple runs"],
      "missing": ["significance test", "random seeds"],
      "issues": []
    },
    "experiment_fairness": {
      "score": 3.0,
      "comment": "...",
      "issues": [],
      "hidden_footnotes": [{"table": "Table 2", "note": "† uses additional data"}]
    }
  },
  "sota_check": {"attempted": true, "source_available": true, "note": "..."},
  "overall_technical_score": 3.5,
  "confidence": 0.8,
  "recommendations": ["конкретные, по приоритету"]
}
```

**Acceptance (детерминированно проверяет оркестратор):**
- Все 4 `dimensions.*.score` ∈ [1.0, 5.0]; вне диапазона → артефакт отклонён.
- Каждый `issue.severity` ∈ {critical, major, minor}; `location` непустой.
- `overall_technical_score` ∈ [1.0, 5.0] и `confidence` ∈ [0, 1].
- При `sota_check.attempted=true` но `source_available=false` — `SOTA API недоступен` заносится в `status_note`, НЕ выдумываются числа SOTA.
- Если критичных issue нет, но `overall_technical_score < 4` — оркестратор запрашивает пояснение (контракт требует согласованности score с issues).

---

## Контракт 3 — reference-auditor → `reference_audit.json`

**Вход:** `analysis.json` (список `references`), topic/keywords (из `analysis.json`), `--venue`. **Инструменты:** MCP `academic-search` (`verify_references_batch`, `find_missing_citations`, `search_related_work`), WebSearch.

```json
{
  "status": "success | partial",
  "status_note": "str (при partial: какой источник недоступен)",
  "verification": {
    "total": 42, "verified": 30, "mismatch": 5, "not_found": 7,
    "details": [
      {
        "reference_index": 0,
        "title": "...",
        "status": "verified | mismatch | not_found",
        "discrepancies": [{"field": "year", "claimed": "2016", "found": "2015"}],
        "sources_checked": ["crossref", "dblp", "semantic_scholar"]
      }
    ]
  },
  "missing_citations": [
    {"title": "...", "year": 2026, "citation_count": 312, "why_matters": "...", "tier": "T1 | T2 | T3"}
  ],
  "related_work_coverage": {"score": 3.5, "comment": "...", "gaps": ["направление X не покрыто"]},
  "citation_quality": {
    "self_citation_ratio": 0.07,
    "recent_ratio_2y": 0.35,
    "venue_balance": "норм / перекос в одну группу / ...",
    "comment": "..."
  },
  "overall_score": 3.5,
  "confidence": 0.8,
  "recommendations": ["добавить ссылки на ...; уточнить года для ..."]
}
```

**Acceptance (детерминированно проверяет оркестратор):**
- `verification.verified + mismatch + not_found == verification.total` — обязательное равенство; иначе артефакт отклонён.
- `len(verification.details) == verification.total`; каждый `reference_index` < total.
- `related_work_coverage.score`, `overall_score` ∈ [1.0, 5.0]; `confidence` ∈ [0, 1].
- `missing_citations[].tier` ∈ {T1, T2, T3}; при T1 всегда обязателен `why_matters`.
- При недоступности Semantic Scholar (rate 429) — в `status_note`, missing_citations могут опираться на CrossRef/веб, НЕ блокируются.

---

## Контракт 4 — paper-comparator → `competitor_analysis.json`

**Вход:** `analysis.json` (task/dataset/метод), окно «последние 12 месяцев», `--venue`. **Инструменты:** MCP `academic-search` (`search_related_work`, `find_competing_methods`, `get_sota_results`, `find_missing_citations`), WebSearch, arXiv.

```json
{
  "status": "success | partial",
  "status_note": "str",
  "search_params": {
    "task": "change detection",
    "datasets": ["LEVIR-CD"],
    "window": "2025-10 .. 2026-10",
    "sources": ["academic-search", "arxiv.org", "paperswithcode"]
  },
  "tier1": [
    {
      "paper": "Full Title", "venue": "CVPR", "date": "2026-03",
      "core_method": "кратко суть", "backbone": "...", "loss": "...",
      "metric": {"dataset": "LEVIR-CD", "name": "F1", "value": 90.2},
      "cited_by_paper": false,
      "notes": "почему обязательно сравнить"
    }
  ],
  "tier2": [{"paper": "...", "venue": "...", "date": "...", "relation": "тот же task, др. dataset", "cited_by_paper": false}],
  "tier3": [{"paper": "...", "venue": "...", "date": "...", "relation": "схожая технология / обзор"}],
  "technical_comparison": [
    {"competitor": "...", "architecture": "...", "innovation": "...", "loss": "...", "train_strategy": "...", "differences_vs_paper": "..."}
  ],
  "missing_baselines": [{"name": "...", "why_important": "...", "source": "arxiv 2026-09 | paperswithcode"}],
  "sota_position": {
    "verdict": "paper_above_sota | paper_at_sota | paper_below_sota | unclear",
    "comment": "..."
  },
  "conclusion": {"baselines_sufficient": false, "comment": "позиция в конкурентной картине", "recommendations": []},
  "overall_score": 3.0,
  "confidence": 0.8
}
```

**Acceptance (детерминированно проверяет оркестратор):**
- `tier1` непустой при успешном поиске. Каждый tier1 обязан иметь `metric.value` и `cited_by_paper` (bool).
- `missing_baselines` помечены источником (arxiv/год или paperswithcode) — без источника кандидат отбрасывается.
- arXiv-препринты помечаются `"препринт, не проходил рецензирование"` в `notes` — без пометки поле считается неполным.
- `sota_position.verdict` ∈ заданных enum-значений; при сравнении метрик указывается источник (self-reported vs leaderboard) в `comments`.
- `overall_score` ∈ [1.0, 5.0], `confidence` ∈ [0, 1].

---

## Контракт 5 — merge → `merged_scores.json` (делает ОРКЕСТРАТОР, не субагент)

Сшивка результатов Фазы 2 по детерминированным правилам (никакого «суммарного ощущения»).

```json
{
  "paper_title": "...",
  "venue": "CVPR | null",
  "sources": {
    "analysis": "analysis.json",
    "quick_assess": "quick_assess.json",
    "tech": "tech_review.json",
    "audit": "reference_audit.json",
    "competitors": "competitor_analysis.json"
  },
  "dimension_scores": {
    "abstract_motivation_novelty": {"score": 3.5, "source": "tech_review", "note": "..."},
    "technical_correctness": {"score": 3.0, "source": "tech_review"},
    "experiments_statistics": {"score": 3.0, "source": "tech_review"},
    "writing_reproducibility": {"score": 3.5, "source": "orchestrator_proxy", "note": "оценивается оркестратором из analysis.json"},
    "related_work_references": {"score": 3.5, "source": "reference_audit"},
    "competitiveness_sota": {"score": 3.0, "source": "competitor_analysis"}
  },
  "severity_counts": {"critical": 0, "major": 3, "minor": 7},
  "critical_issues": [
    {"agent": "technical-reviewer", "issue_id": "T2", "location": "Eq.5", "summary": "..."}
  ],
  "rebuttal_required": false,
  "verdict": "accept | weak_accept | borderline | weak_reject | reject",
  "overall_score": 3.2,
  "confidence": 0.8,
  "flags": [
    {"flag": "sota_api_unavailable", "function": "не блокирует, понижает confidence конкурентов"},
    {"flag": "network_429_refs", "function": "часть верификации ссылок без S2"}
  ]
}
```

### Детерминированные правила merge (обязательны)

1. **overall_score** = среднее арифметическое по 6 `dimension_scores`, округление до 1 знака.
2. **Вердикт** (дискретная шкала, код оркестратора, не интуиция):
   - `≥ 4.5` → `accept`
   - `≥ 3.8` → `weak_accept`
   - `≥ 3.0` → `borderline`
   - `≥ 2.2` → `weak_reject`
   - `< 2.2` → `reject`
3. **Критический триггер:** любой `critical` issue ЛЮБОГО агента → `verdict` не выше `borderline` (жёсткое ограничение независимо от среднего). `critical=0` при этом не повышает вердикт выше порога среднего.
4. **`rebuttal_required = true`**, если `critical > 0` ИЛИ ≥ 3 `major` issue, ИЛИ `missing_baselines` содержит T1-конкурента.
5. **Флаги** фиксируют ограничения среды (API недоступен, rate-limit) — они понижают `confidence` сшивки (шаг −0.15 за каждый флаг), но не блокируют отчёт.

### Шаблон финального отчёта `Review_Report_<paper>.md`

```markdown
# Рецензия: <title>          [вердикт, overall score, confidence]
**Venue:** CVPR | n/a        **Дата:** YYYY-MM-DD

## Сводка
[2-3 предложения: сильные стороны, главные проблемы, вердикт]

## Быстрая оценка (детерминированная)
[Таблица сигналов из quick_assess.json: тип, свежесть цитат, полнота структуры, анонимность, статистика, эффективность]

## Оценки по измерениям (1–5)
| Измерение | Оценка | Источник |
|---|---|---|
| Аннотация/мотивация/новизна | 3.5 | tech_review |
| Техническая корректность | 3.0 | tech_review |
| Эксперименты и статистика | 3.0 | tech_review |
| Написание и воспроизводимость | 3.5 | оркестратор |
| Related work и ссылки | 3.5 | reference_audit |
| Конкурентность / SOTA | 3.0 | competitor_analysis |

## Критические проблемы
- **[Т2, Eq.5]** описание + рекомендация

## Детали
### Техническая корректность (tech_review.json)
[scores, issues c severity, SOTA-таблица, недостающие базилайны]
### Related work и аудит ссылок (reference_audit.json)
[статистика verified/mismatch/not_found, недостающие цитаты, покрытие]
### Конкуренты и SOTA (competitor_analysis.json)
[Tier-1 таблица, техническое сравнение, позиция относительно SOTA]

## Уверенность рецензента: 0.8   Флаги: [sota_api_unavailable]

## Рекомендации (по приоритету)
1. ...
```

---

## Анти-контракты (что НЕ может быть валидным артефактом)

- Проза вместо JSON — возвращённый текст, не являющийся JSON-схемой, отклоняется оркестратором на повторный диспатч с указанием шаблона.
- Числа вне скоупов (score > 5.0, confidence > 1.0) — автоматический reject.
- Выдуманные SOTA-числа при недоступном API — нарушение контракта (`sota_check.source_available=false` → только качественный комментарий).
- `references` из анализа без `reference_stats` — невозможно проверить полноту → повторный диспатч paper-analyzer.
- Мнение «в целом статья хорошая» вместо score → не score; оркестратор требует числовую оценку с issues.