# RESERCHER — Документ контрактов и архитектуры для анализа

**Профиль:** `/home/orangepi/.hermes/profiles/resercher/`
**Версия архитектуры:** v0.2 (пилот) + блок «Писатель» N9–N12.5
**Дата:** 2026-08-18
**Аудитория:** группа разработчиков — глубокий анализ функционала, не констатации.
**Назначение:** единый источник контрактов, схем данных, интерфейсов и потоков для ревью, расширения и отладки.

> **Принцип №0:** LLM производит свидетельства. КОД принимает решения. Всё, что можно сделать детерминированно — делается детерминированно. Пороги и вердикты пересматривает код по `rules.yaml`, а не модель.

---

## 1. Область и границы

Профиль решает одну задачу: **критическая верификация научных текстов** (отчёты, лонгриды, диссертации, авторефераты, статьи) в домене физики конденсированного состояния (азотирование, РФА, нитридные фазы, кристаллография).

**Границы (что профиль НЕ делает):**
- Не пишет научные тексты с нуля (генерация — отдельный блок «Писатель», и то переписывание по патчам).
- Не переводит.
- Не занимается общей грамматикой.
- Не работает с юридическими/академическими текстами как с жанром (канцелярит там — норма).

**Композиция профиля:**
- **Persona** — `SOUL.md` (персона Фёдора + self-ask + домен).
- **Пайплайн верификации** — `science-auditor-orchestrator` (главный скилл) + узлы 1–3 + трибунал.
- **Блок «Писатель»** — `scripts/writer/` (переписывание по контрактам).
- **MCP-серверы** — `mcp/writer_server.py`, `mcp/literature_server.py`.
- **Детерминированные правила** — `rules.yaml`, `rules_{balanced,lenient,strict}.yaml`.
- **Конфиг LLM** — `config.yaml`, `.env`.

---

## 2. Модель выполнения и провайдеры

**Ключевые параметры `config.yaml` (фактическое состояние):**

| Параметр | Значение |
|---|---|
| `model.provider` | `aitunnel-flash` |
| `model.default` | `deepseek-v4-flash` |
| `model.base_url` | `https://api.aitunnel.ru/v1/` |
| `model.fallback` | `[{"provider": "aitunnel-pro", "model": "deepseek-v4-pro"}]` |
| `toolsets` | `hermes-cli`, `web` |
| `auxiliary.vision` | `qwen3.7-flash` (aitunnel-flash) |
| `delegation.inherit_mcp_toolsets` | `false` |
| `delegation.max_concurrent_children` | `3` |
| `delegation.max_spawn_depth` | `2` |
| `delegation.orchestrator_enabled` | `true` |
| `delegation.subagent_auto_approve` | `true` |

**MCP-серверы (в `config.yaml`):**

| Сервер | Команда | Таймаут | Назначение |
|---|---|---|---|
| `writer` | `writer_server.py` | 60с | атомарная запись артефактов |
| `literature` | `literature_server.py` | 120с | поиск по локальной библиотеке |

**Ключи `.env` (только имена):** `OPENAI_API_KEY`, `AITUNNEL_KEY`, `OLLAMA_API_KEY`.

---

## 3. Пайплайн верификации (Science Auditor)

### 3.1 Поток данных

```
input.txt (TXT/MD, напр. автореферат 21 предложение)
   │
   ▼
[Node 1] run_extractor.sh → claims.json     (ClaimeAI, ~573с, ~0.4₽)
   │
   ▼
[Node 2] stub_verifier.py → verdicts.json   (LLM без источников, ~30с, ~0.1₽)
   │
   ▼
[Node 3] synthesizer.py → final_report.md   (Markdown, ~10с, ~0.05₽)
   │
   ▼
[Реальный pipeline, в итерациях] → пост-обработка → трибунал → финальный отчёт
```

**Метрики пилота (автореферат, RU):** claims_valid 20–30, validation_rate 0.70–0.90, время 300–900с.

### 3.2 Контракты артефактов

**claims.json (Node 1):**
```json
{
  "status": "success",
  "claims": {
    "validated": [{"text": "...", "original_sentence": "...", "index": 0}],
    "discarded": [{"text": "...", "reason": "..."}]
  },
  "statistics": {
    "sentences_detected": 21, "claims_validated": 28,
    "claims_discarded": 5, "validation_rate": 0.848
  },
  "processing_time_sec": 573
}
```

**verdicts.json (Node 2):**
```json
{
  "status": "success",
  "verdicts": [
    {"claim_id": 0, "claim_text": "...", "verdict": "UNSUPPORTED",
     "confidence": 0.3, "reason": "..."}
  ],
  "statistics": {"total": 28, "supported": 5, "contradicted": 2,
                 "unsupported": 18, "ambiguous": 3}
}
```

**Шкала вердиктов (Node 2/3):** `SUPPORTED` / `CONTRADICTED` / `UNSUPPORTED` / `AMBIGUOUS`.

**final_report.md (Node 3):** Markdown с цветовой кодировкой — 🟢 SUPPORTED, 🟡 UNSUPPORTED, 🔴 CONTRADICTED, 🟠 AMBIGUOUS + сводка + вопросы автору.

---

## 4. Детерминированный пост-процессор (rules.yaml)

**Архитектура решения:** LLM даёт *предварительный* вердикт. `post_processor.py` применяет `rules.yaml` и выдаёт *окончательный* вердикт. Код — единственный арбитр.

### 4.1 Пороги confidence

| Ключ | Значение | Значение |
|---|---|---|
| `thresholds.supported` | `0.8` | ≥ → SUPPORTED |
| `thresholds.ambiguous` | `0.6` | 0.6–0.8 → AMBIGUOUS |
| `thresholds.problematic` | `0.6` | < → problematic_thesis |
| `thresholds.tribunal_trigger` | `0.8` | advocate conf ≥ → не запускать L5 |

### 4.2 Пересчёт вердикта (после caveat-капов)

| Условие | Действие | reason |
|---|---|---|
| confidence < 0.6 | `set_verdict: UNSUPPORTED` | confidence_below_problematic_threshold |
| confidence 0.6–0.8 | `set_verdict: AMBIGUOUS` | confidence_in_ambiguous_range |

### 4.3 Caveat-правила (после advocate)

| Условие | Действие | reason |
|---|---|---|
| critical_caveat | `cap_confidence: 0.6` | critical_caveat_caps_confidence |
| critical_caveat_count ≥ 1 | `trigger_tribunal` | critical_caveat_triggers_tribunal |
| caveats_count ≥ 2 | `mark_problematic` | multiple_caveats_problematic |
| caveats_count ≥ 3 | `cap_confidence: 0.5` | many_caveats_caps_confidence |

### 4.4 Числовые правила (numeric_comparator)

| Условие | Действие | reason |
|---|---|---|
| numeric_mismatch | `set_verdict: UNSUPPORTED`, cap 0.3 | numeric_mismatch_unsupported |
| numeric_partial_match | `cap_confidence: 0.6` | numeric_partial_match_capped |
| qualifier_mismatch | `cap_confidence: 0.5` | qualifier_mismatch_capped |
| no_numeric_data | `cap_confidence: 0.7` | no_numeric_data_capped |

### 4.5 Проблемные тезисы

**Условия:** verdict_unsupported, verdict_ambiguous, confidence<0.6, caveats≥2 → `mark_problematic`.

### 4.6 Трибунал (L5)

- **trigger_when:** critical_caveat≥1, verdict_ambiguous_after_postprocess, verdict_contradicted.
- **skip_when:** no_caveats, confidence≥0.8 и нет critical.

### 4.7 Доверие к источникам

| Тип | trust |
|---|---|
| primary / textbook | 0.9 |
| review | 0.75 |
| educational / local_md | 0.7 / 0.75 |
| wikipedia / researchgate | 0.6 |
| blog | 0.3 |
| Все < 0.6 | `cap_confidence: 0.5` |

### 4.8 Обоснованность вердикта

- `justification_required.enabled: true`
- Вердикт без `justification/reason/evidence/rationale` → `fallback_status: OPEN`.
- `open_reason: "verdict_without_justification"`.

### 4.9 Эскалация (резак)

| Параметр | Значение |
|---|---|
| seeds | AMBIGUOUS, UNSUPPORTED, OPEN |
| max_hops | 3 |
| max_nodes | 15 |
| max_tokens | 40000 |
| convergence | min_verdicts 2, min_confidence 0.8, max_dispersion 0.2 |
| cut_off | status OPEN, alarm escalation_cutoff |

---

## 5. Трибунал (tribunal-judge) — сходимость через спор

**Ключевое отличие от калибровки метриками:** сходимость достигается через *независимую дискуссию судей*, а не через подгонку порогов.

**Роли судей:**

| Роль | Вектор | Фокус |
|---|---|---|
| физик | physical | законы, размерности, термодинамика, фазовая диаграмма Fe-N |
| методолог | structural | метод, погрешность, выборка, воспроизводимость |
| скептик | critical | логика, контрпримеры, граничные случаи |
| адвокат | defensive | защита от атак |
| агрегатор | — | взвешивает голоса |

**Диалектика (Волна 5):**
- Судьи **атакуют вердикты друг друга** (`attacks[]`), не голосуют «за компанию».
- Противоречие между судьями = зародыш эскалации (новый хоп), не разнобой.
- Вердикт обязан выдерживать атаку; рухнул от первого вызова — недостоин SUPPORTED.
- **Калибровка соседней веткой** (`neighboring_verdicts`): согласие повышает, конфликт → AMBIGUOUS.
- `justification` обязателен (2–4 предложения, ссылка на конкретные факты/источники).

**Агрегатор:** 3:1 → большинство; 2:2 → AMBIGUOUS; ложная сходимость (атака без ответа) НЕ засчитывается как «в пользу автора».

**Формат вердикта судьи:**
```json
{
  "judge_role": "физик", "vote": "SUPPORTED|CONTRADICTED|AMBIGUOUS",
  "confidence": 0.0-1.0, "reasoning": "...", "justification": "...",
  "concerns": [], "attacks": [], "questions_for_author": []
}
```

---

## 6. Блок «Писатель» (N9–N12.5) — S-expression контракты

### 6.1 Поток (state_machine)

Фазы (детерминированный конечный автомат, без LLM):
```
AWAITING_ANSWERS → PLANNING → WRITING → WAVE_A → REVISING → WAVE_B → CONSISTENCY → REVERIFY → REGRESSION → DONE
```
- Каждый переход логируется в `checkpoints[]`.
- Стейт — `writer_state.json` (crash-safe, атомарная запись tmp+os.replace).
- Бюджет: `max_cost_rub=20.0` (config), per-iteration, conservation law `Σ budgets ≤ cell-budget`.

**Структура стейта (EMPTY_STATE):**
```json
{
  "_meta": {"version": 1, "discussion_id": "", "document": "", "created_at": "", "updated_at": "", "profile": "resercher"},
  "cycle": {"iteration": 0, "phase": "AWAITING_ANSWERS", "total_iterations_max": 3, "stop_reason": null},
  "text_versions": {"original": "", "current": "", "history": []},
  "questions": {}, "patches": {}, "verdicts_flow": {}, "regression": {},
  "budget": {"spent_tokens": 0, "spent_cost_rub": 0.0, "max_cost_rub": 20.0, "per_iteration": {}},
  "checkpoints": []
}
```

**Контракты стейта (validate):**
- version == 1, discussion_id не пуст, document не пуст, phase ∈ PHASES+FINAL, iteration ≥ 0, budget ≥ 0.
- question id начинается с `q_`, содержит group_index.
- patch содержит group_index и status.

### 6.2 S-expression движок (`sexpr.py`)

Без зависимостей (~150 строк). Типы: SExpr(head, *args), SAtom, nil, #t/#f, числа, ключевые слова `:k`, комментарии `;`.
API: `parse`, `parse_many`, `format_sexpr`, `make_contract`, `make_patch`, `make_change`, `make_message`.
Предикаты: `has_marker`, `not_pred`, `and_pred`, `or_pred`, `in_scope`, `has_answer`, `verdict_is`.

**Формат контракта:**
```
(contract <type>
  (input (field . "описание") ...)
  (output (field . "описание") ...)
  (criteria (hard (criterion) ...) (soft (criterion) ...))
  (on-fail (action) ...)
  (resource-budget (max-tokens N) (max-cost-rub X)))
```

### 6.3 Реестр контрактов (`contracts.py`)

| Контракт | Роль | Вход | Выход | HARD-критерии |
|---|---|---|---|---|
| `base` | базовый | — | — | conservation law, on-fail |
| `writer` | генератор | pattern, vector, claims, answers, facts | patch-diffs, justification, used-answers | only-own-claims, numbers-from-answers, no-content-deletion, justification-required |
| `critic` | скептик | pattern, vector, diff, neighbors | attacks, verdict, confidence | attacks-nonempty, competence-respected |
| `reviewer` | рецензент | block, criteria-list, neighbor-verdicts | review(verdict, criteria, conflicts) | verdict-justified, conflict-flagged |
| `editor` | редактор | diff, style-rules | suggested-text, edits | meaning-preserved, no-new-facts |
| `proofreader` | корректор | text, answers | corrections, ok | json-valid, numbers-consistent, units-correct |
| `consistency` | приёмка | patches, schema | schema-ok, skeptic-ok, issues | schema-valid, justification-present, no-content-loss |
| `reverify` | повторная верификация | slice, original-verdicts | status-flow, new-caveats, regression-flag | t0-deterministic, no-new-critical |
| `regression` | регрессионный гейт | slice, golden | ks-p-value, semantic-agreement, conformal-set | ks-stable, conformal-gate |

**Conservation law:** `Σ budgets ≤ cell-budget` (сумма бюджетов операций ≤ бюджет ячейки).

### 6.4 Writer-оркестратор (`writer_orchestrator.py`)

Сквозной интеграционный скрипт. Фазы:
- **AWAITING_ANSWERS** — ждёт ответы автора на вопросы (`pending_questions`); нет pending → PLANNING.
- **PLANNING** — `plan_patches(verdicts, tribunal, answers)` → план патчей (groups, patches, cells, unanswered). Пишет `patch_plan.sexpr` + `patch_plan.json`. Для каждого патча `add_patch` + `update_patch_status(created, claim_texts, answers)`.
- **WRITING** — для каждого патча `select_writer(issues, registry)` → `llm_call(writer_system, writer_user, role="writer")` → `_extract_writer_output` (patch-diffs + justification) → `update_patch_status(written, ...)`.
- **WAVE_A** — критик + корректор параллельно.
- **REVISING** — правка по атакам.
- **WAVE_B** — редактор + рецензент параллельно.
- **CONSISTENCY** — `consistency_check` (JSON-схема + скептик).
- **REVERIFY** — `compare_verdicts(old, new)`.
- **REGRESSION** — `regression_gateway` (KS + semantic + conformal).

**Рабочий каталог:** `/media/orangepi/1234-5678/AnalisysDataSet/workspace_pipeline/discussions/<id>/`.

**Парсеры LLM-ответов (критично для контрактов):**
- `_extract_writer_output` — ищет узлы `patch-diffs`/`patch-diff`/`patch`, `justification`.
- `_extract_critic_output` — `verdict`, `confidence`, `attack`/`attacks`. Fallback: поиск вердикта в тексте (SUPPORTED/AMBIGUOUS/CONTRADICTED).
- `_extract_proofreader` — `ok` (#t/#f), `corrections`.
- `_extract_editor` — `suggested-text`, `suggestions`.
- `_extract_reviewer` — `verdict`, `confidence`, `conflicts`.

**Нормализация вердиктов:** `SUPPORTED`/`AMBIGUOUS`/`CONTRADICTED` (регистронезависимо); ACCEPT/OK/PASS/TRUE/ВЕРНО → SUPPORTED; иначе AMBIGUOUS.

### 6.5 Регрессионный гейт (`regression_suite.py`)

Сходимость через трибунал (не фиксированные пороги):
1. **KS-тест** — распределение вердиктов перестало значимо меняться → стоп. `d_statistic < critical` (critical = `√(-0.5·ln(α/2)/n)`).
2. **Semantic agreement** — согласие свиты (0.0–1.0), `agreement_ratio × mean_confidence`, вес `semantic_agreement_weight=0.6`.
3. **Conformal** — предсказательный набор `{accept, escalate, defer}` с покрытием ≥ 1−α.

**Порядок рангов вердиктов:** CONTRADICTED(0) < UNSUPPORTED(1) < AMBIGUOUS(2) < SUPPORTED(3) < OPEN(-1).

### 6.6 Конфиг писателя (`writer_config.yaml`)

| Параметр | Значение |
|---|---|
| `llm.provider` | aitunnel |
| `llm.default_model` | deepseek-v4-flash |
| `llm.fallback_model` | deepseek-v4-pro |
| `llm.max_retries` | 2, timeout 120с |
| `temperature.writer/critic/reviewer/editor/proofreader/meta_select/reverify` | 0.3/0.2/0.2/0.3/0.1/0.2/0.0 |
| `max_tokens.writer` | 2048 (critic/reviewer/editor/proofreader 1024, meta_select 512, reverify 2048) |
| `growth` | max_hops 3, max_nodes 15, max_tokens 40000 |
| `regression` | alpha 0.05, conformal_fallback 0.75, majority 0.5, weight 0.6, ks_min_groups 5 |
| `consistency` | hard_min_justification 10, content_loss_threshold 0.3, soft_warnings_to_fail 2 |
| `budget` | max_cost_rub 20.0, per_iteration 5.0, default_cell 0.5, waves_parallel true |
| `meta_select` | min_score 1, use_llm_when_ambiguous true |
| `state` | max_iterations 3 |

---

## 7. Реестр ролей свиты (`writer_registry.yaml`)

### 7.1 Мета-роли (домен-агностичные)

| Роль | Модель | temp | max_tokens | contract | markers |
|---|---|---|---|---|---|
| generator | deepseek-v4-flash | 0.3 | 4096 | writer | переписать, исправить, добавить |
| critic | deepseek-v4-flash | 0.2 | 2048 | critic | атаковать, проверить, противоречие |
| reviewer | deepseek-v4-pro | 0.2 | 2048 | review | рецензировать, критерии, стандарт |
| editor | deepseek-v4-flash | 0.3 | 2048 | edit | отредактировать, стиль, связность |
| proofreader | deepseek-v4-flash | 0.1 | 1024 | proof | скорректировать, числа, единицы |

### 7.2 Доменные писатели (физика КС)

| Писатель | domain | context_vector | Ключевые markers |
|---|---|---|---|
| physicist | condensed_matter_physics | physical | фаз, нитрид, дифракц, решётк, азотирован, xrd, шеррер |
| methodologist | scientific_methodology | structural | метод, погрешност, измерен, выборк, воспроизводим |
| tribologist | tribology | physical | износ, трение, твёрдост, контактн, смазк |
| materials_scientist | materials_science | physical | сплав, сталь, термообработк, мартенсит, аустенит |

### 7.3 Правила выбора писателя

- **Метод:** `overlap_first` (детерминированный оверлеп keywords узла ∩ markers роли, 0₽).
- **Fallback:** `meta_select` (LLM, ~0.02₽), при неоднозначности.
- `meta_select_max_candidates: 3`.

### 7.4 Волны свиты

- **WAVE_A** (после WRITING): critic + proofreader, параллельно.
- **WAVE_B** (после REVISING): editor + reviewer, параллельно.
- **full_suite:** generator, critic, reviewer, editor, proofreader.

### 7.5 Бюджеты

- **per_cell:** max_tokens 40000, max_cost_rub 0.5.
- **Доли:** generator 0.35, critic 0.15, reviewer 0.20, editor 0.15, proofreader 0.15.

---

## 8. MCP-серверы

### 8.1 writer_server.py (запись артефактов)

**Проблема, которую решает:** встроенный `write_file` обрезает контент в длинных tool-call (mid-tool-call stream drop); пути с пробелами/кириллицей ломают bash.

**Инструменты:**

| Инструмент | Сигнатура | Поведение |
|---|---|---|
| `write_artifact` | `(path, content, encoding=utf-8)` | атомарная запись tmp+`os.replace`, создаёт родительские папки, перезаписывает |
| `append_artifact` | `(path, content)` | дописывает в конец, создаёт файл если нет |
| `read_artifact` | `(path)` | читает до 200000 символов, `errors="replace"` |
| `list_artifacts` | `(directory)` | список файлов, не рекурсивно, сортировка |

**Атомарная запись:** `tempfile.mkstemp(dir=parent, prefix=".writer_tmp_")` → `os.replace`. При исключении — unlink tmp, re-raise.

### 8.2 literature_server.py (поиск по библиотеке)

**Инструменты:**

| Инструмент | Поведение |
|---|---|
| `literature_sources(topics, limit=5)` | выбирает источники по тематикам, ранжирует по числу страниц-совпадений |
| `literature_search(query, limit=8, per_source=2)` | полнотекстовый поиск терминов, группировка по источнику, сниппеты 240 символов |
| `literature_topics()` | список тематик (id → label + markers) |
| `literature_status()` | метаданные индекса (sources, indexed_pages) |

**Тематики (из claimeai topics_tree):** alloys, r18_steel, vks10_alloy, 08x18n10t, xrd, rietveld, deconvolution, nitriding, laser, phase_transformations, nitride_phase, carbide_phase, lattice_param, css, w_h, csr_deform, volume_fraction.

**Индекс:** JSONL в `$HERMES_HOME/cache/literature/literature_index.jsonl`, записи `{path, name, page, text}`.

### 8.3 literature_index.py (построение индекса)

- **Источник:** `/media/orangepi/1234-5678/литература/`.
- **Формат:** PDF (PyMuPDF `fitz`) + DJVU (бинарник `djvutxt` из djvulibre-bin).
- **Фокус-папки:** `_СПРАВОЧНИКИ`, `_ФТТ и ХТТ/*`, `Матвед`, `_КНИГИ ПО СПЕКТРОСКОПИИ`, `_ФИЗИЧЕСКАЯ ХИМИЯ`, `текстура`, `решение структур`.
- **Лимиты:** max_pages 1500/файл, MIN_TEXT_CHARS_PER_PAGE=60 (скан-страницы без OCR пропускаются).
- **Выход:** `literature_index.jsonl` + `index_meta.json` (version, sources, indexed_pages, dirs).

---

## 9. Узлы-скиллы пайплайна

### 9.1 node-1-extractor
- **Назначение:** извлечение атомарных claims через ClaimeAI (LangGraph).
- **Команда:** `bash /home/orangepi/projects/claimeai-service/scripts/run_extractor.sh <input.txt> <output.json>`.
- **Ожидаемые метрики:** claims_valid 20–30, validation_rate 0.70–0.90, 300–900с.
- **Известные проблемы:** 50% claims на EN; формулы игнорируются; NLTK для RU некорректен (нужен natasha); PYTHONSAFEPATH=1 обязателен; запуск из /tmp.

### 9.2 node-2-stub-verifier
- **Назначение:** вердикты через deepseek-v4-flash БЕЗ реальных источников (заглушка пилота).
- **Команда:** `python3 .../stub_verifier.py <claims.json> <verdicts.json>`.
- **Ограничение:** без источников confidence низкий (0.2–0.4).
- **Что заменит:** OpenAlex, CrossRef, arXiv, OpenCitations, Unpaywall, Sci-Bot.

### 9.3 node-3-synthesizer
- **Назначение:** финальный Markdown-отчёт.
- **Команда:** `python3 .../synthesizer.py <verdicts.json> <final_report.md>`.
- **Структура:** сводка → детали по claims → рекомендации → вопросы автору.

---

## 10. Узлы-субагенты (для анализа оркестратором)

### 10.1 science-auditor-orchestrator (главный)
**Паттерн delegate_task (реальная схема Hermes):**
- `delegate_task(goal=..., context=..., role="leaf")` — без `toolsets` и позиционных ролей.
- Субагент читает свой SKILL.md по абсолютному пути в `goal`.
- Параллельные — через `tasks=[...]` batch.
- `hermes -z` — синхронное делегирование; интерактивный — фоновое.

**Workflow (Шаги 0–2):**
- **0:** подготовка (input.txt → claims.json → инициализация JSON-баз).
- **1:** цикл по claims:
  - 1a digestor (контекст по вектору)
  - 1b literature-searcher (локальный корпус ПЕРВЫМ, потом OpenAlex/CrossRef/arXiv)
  - 1c fact-checker (preliminary verdict + caveats)
  - 1d numeric_comparator (ДЕТЕРМИНИРОВАННО: match/mismatch/partial/qualifier/no_data)
  - 1e внутренняя дискуссия (3 вопроса скептика + кросс-валидация векторов)
  - 1f advocate (если conf<0.8 или важный; critical caveat → НЕ SUPPORTED)
  - 1g post_processor (ОБЯЗАТЕЛЕН — финальный вердикт)
  - 1h tribunal (если trigger_tribunal)
  - 1i проблемные тезисы
  - 1j накопление (memory, knowledge_base, established_facts)
- **2:** synthesizer-agent → финальный отчёт (сводка + детали + противоречия + ВОПРОСЫ + ПРОБЛЕМНЫЕ ТЕЗИСЫ + рекомендации).
- **3:** сохранение (final_report.md, verdicts_processed.json, problematic_theses.json).

**Критические правила оркестратора:**
1. LLM verdict — предварительный; окончательный — после post_processor.
2. post_processor обязателен для каждого verdict.
3. numeric_comparator обязателен для claims с числами.
4. advocate: critical caveat → НЕ SUPPORTED.
5. searcher: локальный корпус ПЕРВЫМ.
6. **Детектор размазывания:** >5 tool-вызовов на один claim без делегирования → СТОП, делегируй.
7. context-digestor — ПЕРЕД каждым субагентом.
8. Субагент не знает свой SKILL.md — дай путь в goal.
9. Синтаксис delegate_task — только goal/context/tasks/role.

### 10.2 tribunal-judge
- **mode:** subagent.
- Роли: физик/методолог/скептик/адвокат/агрегатор (паттерн узла задаёт фокус/вопрос/путь).
- Персона: оппонент на защите диссертации, не сикофант.
- Диалектика: атака чужих вердиктов, калибровка соседней веткой, обязательный justification.
- **justification_check:** вердикт без justification → OPEN.

---

## 11. Блокировки, известные ограничения, костыли

### 11.1 Костыли пилота (README.md профиля)
- Без парсера DOCX/PDF (только TXT/MD) — **для статей нужен внешний конвертер**.
- Без пост-процессора ClaimeAI (RU-фильтр).
- Stub-verifier без реальных источников.
- Без Mathpocalypse / Devil's Advocate / Tribunal в Node 3.
- Без quality gates (Hermes сам оценивает).
- Без чекпоинтов/resume (у блока «Писатель» ЕСТЬ; у пайплайна верификации — нет).
- Без хешей артефактов.

### 11.2 Известные проблемы Node 1 (ClaimeAI)
- 50% claims на EN (модель обучена на EN) — нужен RU-пост-процессор.
- Формулы игнорируются — нужен отдельный парсер.
- NLTK для RU некорректен — нужен natasha.
- PYTHONSAFEPATH=1 обязателен (NLTK блокирует defusedxml).

### 11.3 Бюджетные ограничения
- `state.max_iterations=3`, `budget.max_cost_rub=20.0` (блок «Писатель»).
- per-cell budget 0.5₽; доли ролей заданы в writer_registry.

---

## 12. Интерфейсы и точки расширения

### 12.1 Что уже есть
- **Детерминированные решения:** rules.yaml, post_processor.py, numeric_comparator.py, state_machine.py, KS-тест, conformal.
- **Контракты:** S-expression контракты 9 типов (contracts.py).
- **Атомарная запись:** writer_server.py (MCP).
- **Литература:** literature_server.py + index (MCP).
- **Сходимость через трибунал:** tribunal-judge + regression_gateway.

### 12.2 Куда расширять (по README «Что добавим в итерациях»)
1. Пост-процессор ClaimeAI (RU-фильтр, merge диапазонов).
2. Node 2 → реальные источники (OpenAlex + CrossRef + arXiv).
3. Deterministic filters (глоссарий, числа, формулы).
4. Quality gates (пороги, warnings, errors).
5. Чекпоинты (durable state.json, resume) для пайплайна верификации.
6. Node 3 Devil's Advocate (Mathpocalypse, 3 sub-nodes).
7. Ремонтные стратегии.
8. Node 4 Tribunal Scoring (CAJAL).
9. Прогон на полном автореферате (88 КБ).
10. Bridge Protocol v0.1.1 (опционально).

---

## 13. Сводная схема компонентов и их контрактов

| Компонент | Тип | Вход | Выход | Детерминированный? |
|---|---|---|---|---|
| Node 1 (ClaimeAI) | внешний | input.txt | claims.json | частично (LLM) |
| Node 2 (stub) | скрипт | claims.json | verdicts.json | LLM |
| Node 3 (synth) | скрипт | verdicts.json | final_report.md | LLM |
| post_processor | код | verdict.json + rules.yaml | verdict_processed.json | ✅ |
| numeric_comparator | код | claim + sources | match/mismatch/... | ✅ |
| tribunal-judge | subagent | claim + sources + context | verdict JSON | LLM-спор |
| writer_orchestrator | код | verdicts + answers | writer_state.json + patches | ✅ (движок) / LLM (генерация) |
| state_machine | код | state | phase transitions | ✅ |
| regression_gateway | код | slice + golden | ks + semantic + conformal | ✅ |
| writer_server (MCP) | сервер | path/content | атомарный файл | ✅ |
| literature_server (MCP) | сервер | topics/query | источники/сниппеты | ✅ (поиск) |

---

## 14. Ключевые принципы для ревью

1. **LLM даёт свидетельства, код решает.** Любое изменение, переносящее решение из кода в LLM, — регрессия.
2. **Сходимость через трибунал, не метрики.** Пороги в rules.yaml — инженерная калибровка, а не оценка качества.
3. **Контракты обязательны.** Вердикт без justification → OPEN. Патч без justification → reject.
4. **Атомарность.** Все записи — tmp + os.replace (writer_server, state_machine).
5. **Анти-сикофантия.** Персона и критика вшиты: «артефакт сильнее слов», скептик обязан атаковать.
6. **Conservation law писателя:** `Σ budgets ≤ cell-budget`.
7. **Ограничение токенов.** max_tokens/температура зафиксированы в writer_config.yaml — менять только с обоснованием.
8. **Трибунал = спор, не голосование.** Ложная сходимость (атака без ответа) — понижение вердикта.
