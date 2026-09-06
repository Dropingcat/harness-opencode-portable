# Research Orchestration Process — общий контракт

> Общая методология для всех агентов исследовательского цикла. **Читать ЭТОТ файл первым** перед любой задачей. На него ссылаются research-orchestrator, claim-parser, source-fetcher, fact-checker, tribunal-judge, synthesizer.

## Принцип №0

**LLM производит свидетельства. КОД принимает решения.** Всё, что можно сделать детерминированно — делается детерминированно. Вердикты пересматривает код (Hermes-скрипты), а не модель.

Это не реклама. Это контракт: если LLM-вердикт противоречит детерминированной проверке (numeric mismatch, dimension mismatch, no justification) — код побеждает.

## Граф агентов

```
            ┌──────────────────────────┐
            │  research-orchestrator   │  primary, user-invocable
            │  (оркестратор цикла)      │
            └──────────┬───────────────┘
                       │ delegate_task (batch/sequential)
       ┌───────────────┼────────────────────────┐
       ▼               ▼                        ▼
┌─────────────┐ ┌──────────────┐        ┌──────────────────┐
│ claim-parser │ │ source-fetcher│       │  fact-checker    │
│ (атомарные   │ │ (browser-MCP + │       │  (verdict +      │
│  клаймы)     │ │  research_    │       │  Hermes numeric/ │
└─────────────┘ │  papers)       │       │  evidence/post)  │
                └──────────────┘        └──────────────────┘
                       │                          │
                       └──────────┬───────────────┘
                                  ▼
                        ┌──────────────────┐
                        │  tribunal-judge   │  (если trigger)
                        │  (диалектика)     │
                        └────────┬─────────┘
                                 ▼
                        ┌──────────────────┐
                        │   synthesizer     │
                        └──────────────────┘
```

**Правило диспатча:** оркестратор вызывает субагентов через `task` с полным контрактом в `prompt`. Субагент не знает свой SKILL.md — дай путь и цель в prompt.

## Инструменты

| Инструмент | Назначение | Кто использует |
|---|---|---|
| `webfetch` | Чтение известного URL → markdown | source-fetcher |
| `research_papers` | arXiv + OpenAlex поиск статей | source-fetcher |
| `browser_fetch` / `browser_search` / `browser_extract_text` / `reddit_search` | Веб-поиск/извлечение через Playwright+DDG+Reddit (browser-MCP) | source-fetcher |
| `bash` | Вызов Hermes-скриптов (детерминированный слой) | orchestrator, fact-checker |
| `read` | Чтение артефактов/протоколов | все |
| `write` / `edit` | Запись артефактов в рабочую папку | orchestrator, synthesizer |
| `todowrite` | Трекинг этапов | orchestrator |
| `task` | Диспатч субагентов | orchestrator |

> **Порядок источников (жёсткий):** локальный корпус (если есть) → arXiv/OpenAlex → веб (browser-MCP). Локальный ПЕРВЫМ — это правило из Hermes resercher, оно снижает расход токенов.

## Контракты данных (JSON-артефакты)

Все артефакты пишутся в рабочую папку `${RESEARCH_WORKSPACE:-${OPENCODE_RUNS_DIR}/research-<ts>/}`. Оркестратор создаёт папку и передаёт путь субагентам.

### 1. ResearchTask (вход в цикл поиска)

Создаётся оркестратором для спорного клайма. Передаётся source-fetcher'у.

```json
{
  "task_id": "rt_<n>",
  "claim_ids": [0, 3, 7],
  "claim_texts": ["..."],
  "question": "Какова энтальпия активации азотирования Fe2-3N?",
  "why_it_matters": "Тезис C3 опирается на это число; расхождение ±20% → CONTRADICTED",
  "preferred_source_classes": ["primary", "textbook", "review"],
  "max_cost_rub": 1.5,
  "status": "pending"
}
```

### 2. Claim (после claim-parser)

```json
{
  "claims": {
    "validated": [
      {"text": "атомарный клайм", "original_sentence": "...", "index": 0, "claim_type": "numeric|qualitative|definition|methodological", "importance": "critical|high|medium|low"}
    ],
    "discarded": [{"text": "...", "reason": "..."}]
  },
  "statistics": {"sentences_detected": 21, "claims_validated": 28, "validation_rate": 0.848}
}
```

### 3. Source / Evidence (после source-fetcher)

```json
{
  "sources": [
    {"source_id": "slug", "title": "...", "url": "...", "doi": "...", "type": "primary|textbook|review|web|blog", "trust": 0.9, "abstract": "...", "excerpt": "фрагмент ≤ 2000 символов", "found_via": "arxiv|openalex|browser_ddg|browser_reddit|literature_local"}
  ],
  "rejected_sources": [{"title": "...", "reason": "нерелевантен/низкий trust"}],
  "queries_used": ["..."],
  "task_id": "rt_0"
}
```

### 4. Verdict (после fact-checker, ДО детерминированной пост-обработки)

```json
{
  "verdicts": [
    {
      "claim_id": 0, "claim_text": "...",
      "verdict": "SUPPORTED|CONTRADICTED|UNSUPPORTED|AMBIGUOUS|OPEN",
      "confidence": 0.0, "reason": "...", "justification": "2-4 предложения со ссылкой на источник",
      "sources_used": [{"source_id": "...", "title": "...", "relevance": 0.89}],
      "caveats": [{"severity": "critical|warning|info", "text": "..."}],
      "numeric_comparison": {"claim_value": "77", "source_value": "70-80", "deviation": "в диапазоне", "status": "match|partial_match|mismatch|no_data|dimension_mismatch"}
    }
  ]
}
```

### 5. Verdict (после детерминированной пост-обработки Hermes)

Выход `post_processor.py` + `numeric_comparator.py` + `evidence_contract.py`. **Окончательный вердикт.**

```json
{
  "verdicts": [
    {"claim_id": 0, "...предыдущие поля...", "final_verdict": "SUPPORTED", "final_confidence": 0.6, "postprocess_reasons": ["numeric_partial_match_capped", "confidence_in_ambiguous_range"], "evidence": [{"source_id": "...", "span": "...", "trust": 0.9, "type": "primary"}]}
  ]
}
```

### 6. TribunalReport (если триггер)

```json
{
  "claim_id": 0,
  "judges": [
    {"judge_role": "физик|методолог|скептик|адвокат|агрегатор", "vote": "SUPPORTED|CONTRADICTED|AMBIGUOUS", "confidence": 0.0, "reasoning": "...", "justification": "...", "concerns": [], "attacks": [], "questions_for_author": []}
  ],
  "aggregate_verdict": "SUPPORTED|CONTRADICTED|AMBIGUOUS|OPEN",
  "final_confidence": 0.0
}
```

## Детерминированный слой (Hermes-скрипты)

**Runner** (`run_research.sh`) вызывает эти скрипты в строгом порядке. **Код — единственный арбитр окончательного вердикта.** Агенты НЕ вызывают эти скрипты сами (кроме numeric_comparator в fact-checker — но в текущей архитектуре это делает runner в BRICK 4).

| Скрипт | BRICK | CLI | Вход → Выход | Когда |
|---|---|---|---|---|
| `numeric_comparator.py` | 4 | `python3 numeric_comparator.py <verdicts.json> <sources.json> <out.json>` | verdicts + sources → numeric signal | ВСЕГДА (числа или нет — детектит сам) |
| `merge_numeric.py` | 4 | `python3 merge_numeric.py <verdicts.json> <numeric_result.json> <out.json>` | verdicts + numeric → verdicts_enriched | ВСЕГДА после numeric_comparator (без него numeric_rules мертвы) |
| `evidence_contract.py` | 5 | `python3 evidence_contract.py <verdicts.json> <rules.yaml> <out.json>` | verdicts + rules → evidence[] | ВСЕГДА (provenance) |
| `post_processor.py` | 5 | `python3 post_processor.py <verdicts.json> <rules.yaml> <out.json>` | verdicts + rules → final verdicts | ВСЕГДА — даёт final_verdict |
| `justification_check.py` | 6 | `python3 justification_check.py <verdicts.json> <rules.yaml> <out.json> --report <alarms.json>` | verdicts + rules → OPEN без обоснования | ВСЕГДА после post_processor (отдельный шаг, НЕ внутри post_processor) |
| `escalation.py` | 7 | `python3 escalation.py <verdicts.json> <topics_tree.json> <rules.yaml> <out.json>` | verdicts + topics + rules → stop status | ВСЕГДА (stop criteria кодом: max_hops/convergence/alarms) |
| `factcheck_guard.py` | 3 | `python3 factcheck_guard.py <verdicts.json> --mark-parse-fail --out <out.json>` | verdicts → санитизированные verdicts | ВСЕГДА после fact-checker (санитизация LLM-сбоев) |
| `judge_brief.py` | 8 | `python3 judge_brief.py <verdicts.json> <out.json>` | verdicts → 5 брифов/claim | ПЕРЕД трибуналом (если триггер) |
| `synthesizer.py` | 9 | `python3 synthesizer.py <verdicts.json> [tribunal.json] <report.md>` | verdicts(+tribunal) → md | ВСЕГДА в конце |
| `circularity.py` | 2 | `python3 circularity.py --json --document <doc> <source_excerpt> <claim_text>` | excerpt + claim → origin | Для каждого source (anti-self-confirmation) |

**Пути:**
- Скрипты: `${RESEARCH_SCRIPTS_ROOT}`
- Verification: `${RESEARCH_VERIFICATION_ROOT}` (circularity, content_verdict, cascade)
- Rules: `${RESEARCH_RULES_PATH}` (по умолчанию; strict/lenient — альтернативы)
- Runner: `${RESEARCH_RUNNER_SH}`
- Рабочая папка: `${RESEARCH_WORKSPACE}` (создаёт runner)

## Пороги (из rules.yaml)

- `thresholds.supported: 0.8` — ≥ → SUPPORTED
- `thresholds.ambiguous: 0.6` — 0.6–0.8 → AMBIGUOUS
- `thresholds.problematic: 0.6` — < → problematic
- `thresholds.tribunal_trigger: 0.8` — advocate conf ≥ → не запускать трибунал
- Numeric: ±10% → SUPPORTED, >20% → CONTRADICTED; dimension_mismatch → UNSUPPORTED cap 0.3
- Trust источников: primary/textbook 0.9, review 0.75, educational 0.7, wikipedia/researchgate 0.6, blog 0.3; все <0.6 → cap 0.5

## Шкала вердиктов

`SUPPORTED` (зелёный) · `CONTRADICTED` (красный) · `UNSUPPORTED` (жёлтый) · `AMBIGUOUS` (оранжевый) · `OPEN` (серый — нет justification / недостаточно данных)

## Триггер трибунала

- `critical_caveat ≥ 1`
- `verdict = AMBIGUOUS` после пост-обработки
- `verdict = CONTRADICTED`
- НЕ запускать если: `no_caveats` AND `confidence ≥ 0.8`

## Бюджет

- `max_cost_rub` на задачу (по умолчанию 1.5₽/claim, 20₽/документ) — параметр runner'а `--max-cost-rub`.
- Runner трекает расход после каждого агента (парсит cost из вывода opencode). При превышении → STOP + escalation_cutoff.
- `max_iterations` — параметр runner'а `--max-iterations` (в текущей версии конвейер однопроходный; параметр зарезервирован для будущей многоитерационной версии).

## Stop criteria (кодом, не промпт)

Runner контролирует stop criteria детерминированно через `escalation.py` (BRICK 7):
- `max_hops` (по умолч. 3), `max_nodes` (15), `max_tokens` (40000)
- convergence: `min_verdicts 2, min_confidence 0.8, max_dispersion 0.2`
- При срабатывании → status OPEN + alarm escalation_cutoff
- Бюджет: при `spent > max_cost_rub` → STOP

«Детектор размазывания >5 tool-вызовов» — устаревший промпт-механизм; в текущей архитектуре runner ведёт цикл и не даёт LLM «размазываться» — каждый LLM-шаг инкапсулирован в BRICK с детерминированными гейтом до и после.

## Поток данных — BRICKS-runner (детерминированный контроль цикла)

> **Принцип организации:** Цикл ведёт детерминированный runner (`run_research.sh`), НЕ LLM-оркестратор. Runner валидирует схемы артефактов (блокирующе), вызывает детерминированные скрипты в строгом порядке, трекает бюджет/хопы кодом, парсит ответы search-сервера кодом, логирует audit. Агенты — LLM-узлы внутри runner'а. Оркестратор-агент — интерфейс пользователя к runner'у.

```
input.txt
   │
   ▼ BRICK 1 SPLIT:   [claim-parser agent] → claims.json + валидация схемы (блок)
   │
   ▼ BRICK 2 SEARCH:  [source-fetcher agent] per claim → sources_<id>.json
   │                   + детерминированный парсер ответов (blocked/http_status/excerpt → reject)
   │                   + circularity-гейт (пересказ документа → понижение trust)
   │                   + clamp trust ∈ [0,1]
   │
   ▼ BRICK 3 VERDICT:  [fact-checker agent] → verdicts_raw.json
   │                   + factcheck_guard (санитизация LLM-сбоев парсинга)
   │                   + валидация схемы (блок)
   │
   ▼ BRICK 4 NUMERIC:  numeric_comparator.py → numeric_result.json
   │                   + merge_numeric.py → verdicts_enriched.json (ПОЧИНКА мёртвой связки!)
   │                     (без merge numeric_rules в post_processor — мёртвый код)
   │
   ▼ BRICK 5 EVIDENCE+POST: evidence_contract.py (provenance, clamp trust)
   │                        + post_processor.py → verdicts_final.json (ОКОНЧАТЕЛЬНЫЙ вердикт)
   │
   ▼ BRICK 6 JUSTIFY: justification_check.py (без обоснования → OPEN) [ПОЧИНКА — отдельный шаг]
   │                  + alarms.json
   │
   ▼ BRICK 7 ESCALATE: escalation.py (stop criteria: max_hops/convergence/alarms) [ПОЧИНКА — кодом]
   │                   + escalation_out.json
   │
   ▼ BRICK 8 TRIBUNAL: (если триггер AMBIGUOUS/CONTRADICTED/critical_caveat)
   │                   judge_brief.py → judge_briefs.json
   │                   [tribunal-judge agent] → tribunal_combined.json
   │
   ▼ BRICK 9 SYNTHESIZE: synthesizer.py (база) + [synthesizer agent] (расширение)
   │                     → final_report.md
   │
   ▼ BRICK 10 AUDIT: run/<ts>/summary.json (input_hash → decision → output → ts для каждого BRICK)
```

**Имена файлов (жёсткие, runner использует их):**
- `claims.json` — выход claim-parser
- `sources_<claim_id>.json` — выход source-fetcher per claim
- `sources_index.json` — агрегация всех sources для numeric_comparator
- `verdicts_raw.json` — выход fact-checker (предварительные вердикты)
- `numeric_result.json` — выход numeric_comparator
- `verdicts_enriched.json` — выход merge_numeric (raw + numeric)
- `evidence_out.json` — выход evidence_contract (provenance)
- `verdicts_final.json` — выход post_processor (ОКОНЧАТЕЛЬНЫЙ вердикт) + justification_check
- `judge_briefs.json` — выход judge_brief
- `tribunal_combined.json` — выход tribunal-judge
- `final_report.md` — финальный отчёт
- `run/<ts>/_audit.json` — audit-лог каждого BRICK
- `run/<ts>/summary.json` — сводка прогона

## Детерминированные гейты runner'а (контроль кодом, не промпт)

| Гейт | Что проверяет код | Действие при провале |
|---|---|---|
| Валидация схем | claims/sources/verdicts соответствуют JSON-контракту (поля, enum, типы) | `sys.exit(2)` — блок, не warning |
| trust clamp | trust ∈ [0,1] для каждого source/evidence | clamp + warning |
| Парсер search-ответов | `blocked==true` / `http_status>=400` / пустой excerpt → reject | source в rejected_sources |
| circularity | источник-пересказ документа → `origin=document_derived` | понижение trust до 0.3 |
| factcheck_guard | LLM-сбой парсинга в verdict | mark_parse_fail (не «критичное свидетельство») |
| merge_numeric | numeric_result влит в verdicts | без него numeric_rules мертвы |
| justification_check | вердикт без justification | verdict → OPEN + alarm |
| escalation | max_hops/convergence/dispersion | STOP + escalation_cutoff |
| budget | spent > max_cost_rub | STOP + escalation_cutoff |
| audit | input_hash → decision → output → ts | записывается в _audit.json каждый BRICK |

## Анти-сикофантия

Персона и критика вшиты. Скептик обязан атаковать. «Похоже на правду» — не аргумент. Вердикт обязан выдерживать атаку; рухнул от первого вызова — недостоин SUPPORTED. justification обязателен (2–4 предложения, ссылка на конкретные факты/источники). Вердикт без justification → OPEN (детерминированно, через `justification_check.py`, не промпт).

## Контракты диспатча (runner → субагент)

Runner вызывает субагентов через `opencode run --agent <name>` синхронно:
- `claim-parser`, `source-fetcher`, `fact-checker`, `tribunal-judge`, `synthesizer`
- Prompt содержит: цель, путь к shared-методологии, конкретные данные, формат возврата, путь для записи результата
- Субагент возвращает результат и/или пишет файл в workspace

Субагент не ведёт цикл. Не вызывает другие субагенты. Не вызывает детерминированные скрипты (кроме fact-checker → numeric_comparator). Не контролирует бюджет. Не считает хопы. Это работа runner'а.

## Ограничения

1. **Никогда не пиши продакшн-код или конфиги** — только артефакты исследования.
2. **Не принимай реализации-решения** — сообщай факты и опции; пользователь решает.
3. **Всегда цитируй источники** — каждый клайм трассируем на URL/DOI.
4. **Отмечай чувствительность к версии** — если инфо специфично для версии.
5. **Предпочитай официальные источники** для авторитетных клаймов.
6. **Локальный корпус ПЕРВЫМ** (если есть), потом arXiv/OpenAlex, потом веб.

## Разрешение research-каталога (перенесено из research-process.md, P1.5)

Все персистентные выводы (отчёты, статьи, заметки) идут под единый родительский каталог:

- Если задана переменная окружения `RESEARCH_DIR` — использовать её как родительский.
- Иначе — использовать `research/` в корне текущего проекта.
- В shell: `${RESEARCH_DIR:-research}`. Каждый тип вывода — в свой подкаталог:

| Тип вывода | Подкаталог | Шаблон имени |
|---|---|---|
| Отчёты исследования | `reports/` | `[slug]-[YYYY-MM-DD].md` |
| Заметки знаний | `notes/` | `[slug]-notes.md` |
| Статьи | `articles/` | `[slug]-article-[YYYY-MM-DD].md` |

> **P1.5:** Эта секция заменяет старую `.opencode/shared/research-process.md`, которая переименована в `research-process.deprecated.md` (researcher-агент отключён). Не ссылайся на старый файл.
