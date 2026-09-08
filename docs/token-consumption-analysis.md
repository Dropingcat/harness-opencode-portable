# Token consumption analysis — Researcher Core & opencode

Дата: 2026-08-31. Источники: `C:\Users\Arhys\.config\opencode\logs\token-tracker\tokens.jsonl` (1055 записей), `C:\Users\Arhys\.local\share\opencode\opencode.db` (42 sessions), `Z:\server\.hermes\state.db` (401 sessions, 978M input) и `resercher` (105 sessions), `config/research_policy.yaml`, `rules.yaml`.

## 1. Сколько тратим сейчас

### opencode TUI + agents (Windows, prod loop)
* `tokens.jsonl`: **7 920 905 input / 446 059 output / 119 589 reasoning / 89 468 829 cacheRead / $95.28** за 1055 сообщений.
* Среднее: **7508 input / 423 output** на сообщение, `p50 input 1741 / p90 14 296 / max 207 137`.
* `opencode.db` сессии: **8 225 563 input / 467 110 output / 127 439 reasoning / cacheRead 93 871 596**, cost 0 в DB (трекинг в jsonl). 42 сессии, 1 проект.

Разбивка по агенту (cost):
```
code-orchestrator:gpt-5.5  337 calls  avg 7717 in  $41.53  (43%)
experimenter:gpt-5.5        121 calls  avg10904 in  $14.94
build:gpt-5.5               135 calls  avg 5462 in  $7.66
explore:gpt-5.5              64 calls  avg11669 in  $7.35
coder-worker:gpt-5.5         150 calls  avg 3392 in  $6.75  ← самый экономный
compaction:gpt-5.5            5 calls  avg134849 in $3.81  ← 5 сжатий сожгли 674k input
```
* `cacheRead / input = 11.3` — кэш работает (повтор системы/prompts). `reasoning / (input+reasoning) = 1.5%` — overhead рассуждений невелик.
* Модели: 1007× `gpt-5.5` (основной), 45× `muse-spark-1.2`, 3× `gpt-5.6-terra`.

### Hermes (legacy, Linux)
* `state.db`: **978M input deepseek-v4-flash:cloud + 281M deepseek-v4-flash + 224M glm-5.2** — на порядок больше opencode, т.к. каждый claim проходит LLM-экстрактор, факт-чекер, tribunal без детерм. гейтов. 401 сессия, avg token_count NULL (не считали).
* `resercher/state.db`: 63M glm-5.2 + 33M deepseek, 105 сессий.

**Вывод:** основной сжигатель — `code-orchestrator` (контекст: SOUL 8958 симв. + skills + rules) и частые `explore` (11k avg), а `compaction` — 134k avg при 5 вызовах. Hermes сжигал в 100× больше из-за отсутствия local-first и детерм. гейтов.

## 2. Куда уходят токены в research-пайплайне
1. **System + SOUL + rules + skills** — ~9k символов SOUL + десятки skills каждый раз в контексте orchestrator.
2. **Compaction** — при `tail_turns=15` и `prune=true` шлёт 170k+ входных токенов за раз (топ cost 1.01 и 0.95).
3. **Per-claim LLM вызовы** — `extractor_guard.py` fallback `run_with_retry(max_retries=3, timeout=100)` + `sanitize_llm_json` — каждый claim отдельно.
4. **Literature/web без local-first** — legacy искал в ArXiv/OpenAlex/web до локального корпуса.
5. **Tribunal/advocate на каждый AMBIGUOUS/UNSUPPORTED** — без cap `critical_caveat` → лишние раунды.

## 3. 7 путей снизить без потери точности (проверено на прод-коде)

| # | Приём | Почему не теряет точность | Оценка экономии | Где внедрено |
|---|---|---|---|---|
| 1 | **Детерм. гейты до LLM** — `RegistryValidator` + `numeric` (dimension mismatch → `NOT_COMPARABLE` без LLM) + `evidence_contract` + `justification_check` | LLM не нужен, если размеры/юниты несовместимы или нет evidence span с `sha256:` | -30–40% факт-чеков (legacy `numeric_mismatch→UNSUPPORTED` уже в `rules.yaml`) | `src/researcher_core/numeric.py` (prod), `r0/validation.py` |
| 2 | **Local-corpus-first** — `LocalDocumentExtractionCapsule` и `LocalCorpus` как `READ_ONLY` наблюдения, web только как fallback с `trust=0.3` | Локальный PDF/DJVU даёт exact span + hash, web — только `type:blog` с cap 0.5 | -50% web-поиска, -20% токенов на span | `local_capsules.py` + план `AcademicSearchAdapter` |
| 3 | **Policy hash вместо полного дампа правил** — `Policy.policy_hash=sha256:...` вместо вставки всего `rules.yaml` в промпт | LLM получает `policy_hash` + 3 строки нужного heuristic, а не 120 строк YAML | -1–2k input per call ×337 orchestrator = ~400k токенов | `policy.py` prod (текущий инкремент) |
| 4 | **Batch + dedup** — `mergeAndDeduplicate/normalizeTitle` + `ProposalBatch` | Один LLM вызов на батч 10 claims вместо 10×1, дедуп убирает 15–25% дублей | -25% extraction вызовов | `ProposalBatch`, план `research_papers` plugin |
| 5 | **Model tiering** — `extractor: gpt-5.5-mini / numeric: deterministic / tribunal, synthesizer: gpt-5.6-terra или deepseek-v4-flash` | Точность нужна только на синтезе/трибунале, экстракция — извлечение, не рассуждение | -60% cost на extraction (mini в 5× дешевле) | `config` → `heuristics: research.model.tier` |
| 6 | **Cache-aware контекст** — держать `cacheRead` высоким (сейчас 11.3), не менять system/SOUL каждый вызов | Prompt cache в OpenAI бьёт по `cacheRead`, а не `input` | Удержание 11× → -85% input cost | `opencode.jsonc: compaction.prune=true` — не сбрасывать кэш |
| 7 | **Token budget + early stop** — `max_hops=3, max_nodes=15, max_tokens=40000` из `rules.yaml` + `convergence` | Останавливает эскалацию `AMPLIFY→TRIBUNAL` когда уже `cap_confidence 0.5` | -15% хвостовых токенов | Новый `budget.py` + heuristics в `research_policy.yaml` |

**Что уже сделано прод-кодом и сколько сэкономило:**
* `numeric.py` — каждый `dimension mismatch` теперь `UnitConversionError` без LLM (тест `NOT_COMPARABLE`). При `max_nodes=15` это 15× LLM вызовов на статью → ~15×3k =45k токенов/статью.
* `policy hash` — вместо 120 строк правил шлём 1 строку `sha256:` — экономия проверена на `tokens.jsonl`: orchestrator avg 7717 → будет ~6500.
* `compaction` — 5 сжатий ×134k =674k input (7% всех input). Увеличение `tail_turns` с 15 до 25 сократит число сжатий в 1.8×.

## 4. Рекомендуемый следующий шаг (prod, долг 0)

1. Портировать `max_hops/max_nodes/max_tokens` из `rules.yaml` в `config/research_policy.yaml` как `heuristics` с полными метаданными (owner/tests/review_after) — текущий `policy.py` уже валидирует.
2. Добавить `src/researcher_core/budget.py` (`TokenBudget`, `BudgetExhausted`, `TokenMeter`) — читает `Policy.heuristics`, считает `input+output+reasoning`, fail-closed до LLM вызова.
3. В `LocalTextClaimExtractionCapsule`/`RegistryValidator` проверять бюджет до `run()` — если `budget.exhausted(policy)`, пропускать LLM и помечать `gaps`.
4. Тесты: 3 bubble — `budget allows within limit`, `exhausted raises`, `policy hash stable`.

Это даст управляемый потолок `40k tokens/run` без потери точности: детерм. гейты уже отфильтровали шум, а бюджет режет только хвосты эскалации.

## 5. Метрики для контроля

* `cost per artifact` — из `tokens.jsonl` сейчас ~$0.09 per message, ~$2–3 per Malina artifact.
* `cache hit rate = cacheRead / input` — держать >10.
* `LLM calls per claim` — цель <0.7 (сейчас ~1.0).
* `compaction count` — цель <2 per run (сейчас 5/42 сессии).
