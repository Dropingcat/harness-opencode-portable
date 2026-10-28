# Paper Review Orchestration — инструкции для оркестраторов

Инструкции для оркестратора (primary-агента, исполняющего `/review-paper`, `/pre-screen`, `/rebuttal`), управляющего цепочкой рецензирования из 4 субагентов. Диспатч — через `task` с полным контрактом в `prompt`. Шаблоны контрактов — в `shared/paper-review-chain-contracts.md` (см. там же анти-контракты и acceptance).

> **Правило диспатча (общее для harness):** субагент НЕ знает свой SKILL.md и свой контракт — передай путь к методологии и шаблон JSON целиком в `prompt`. Ни один субагент не вызывает другого — цепочку ведёшь только ты.

## Твой стек

- `task` — диспатч `paper-analyzer`, `technical-reviewer`, `reference-auditor`, `paper-comparator`.
- MCP-инструменты `mcp__paper-parser__*` и `mcp__academic-search__*` — доступны тебе напрямую (например, `ping` для выбора способа парсинга).
- `bash` — детерминированный слой: `python "${OPENCODE_HARNESS_ROOT}/scripts/paper-review/quick-assess.py" <text.md>` → `quick_assess.json`.
- `read`/`write`/`edit` — артефакты в рабочей папке, шаблоны venue-профилей.
- `question` — уточнение `--venue`, если не задан.
- `todowrite` — трекинг стадий.

**Рабочая папка:** создай `${PAPER_WORKSPACE:-${OPENCODE_RUNS_DIR}/paper-review-<ts>/}`. Артефакты — по жёстким именам из контрактов: `analysis.json`, `quick_assess.json`, `tech_review.json`, `reference_audit.json`, `competitor_analysis.json`, `merged_scores.json`, `Review_Report_<paper>.md`.

## Порядок исполнения цепочки (обязательный)

```
1. Подготовка: параметры, venue, workspace, todowrite
2. Фаза 1:   paper-analyzer → analysis.json     [валидация контракта]
3. Фаза 1.5: quick-assess.py → quick_assess.json [детерминировано, без LLM]
4. Фаза 2:   ПАРАЛЛЕЛЬНЫЙ диспатч 3 субагентов (в одном ходе task):
             technical-reviewer + reference-auditor + paper-comparator
5. Фаза 3:   сшивка → merged_scores.json → Review_Report_<paper>.md
6. Выдача:   краткая сводка + путь к отчёту
```

## Детали фаз

### Фаза 0 — подготовка

1. Разбери параметры `$ARGUMENTS`: `<pdf_path>`, `--venue`, `--with-code`, `--with-supplement`. PDF обязан существовать; иначе остановись с вопросом.
2. Если venue не задан — спроси через `question`. Знаешь venue? Загрузи контекст:
   - `${OPENCODE_HARNESS_ROOT}/skills/opencode-current/paper-review/references/venue-profiles.md`
   - `${OPENCODE_HARNESS_ROOT}/skills/opencode-current/paper-review/references/venue-review-criteria.md`
   - перспективы рецензентов `${OPENCODE_HARNESS_ROOT}/docs/reviewer-perspectives/<NN>-<venue>-reviewer.md`
3. Скопируй venue-специфичные критерии в prompt каждого субагента Фазы 2 (какие веса/чек-листы применить).

### Фаза 1 — paper-analyzer (должна выполниться первым, результат нужен всем)

**prompt** субагенту: путь к PDF, путь методологии (`shared/paper-review-chain-contracts.md`), требуемое имя выхода `analysis.json`, acceptance из контракта 1. Передай `--venue`-контекст, если есть.

До диспатча проверь доступность MCP `mcp__paper-parser__ping`. При ошибке — скажи субагенту использовать fallback Read постранично (до 20 стр.) и ручное извлечение ссылок; результат всё равно должен быть валидным `analysis.json`.

**Валидация контракта 1** (детерминированная, до Фазы 2): файл существует, `status=success`, `markdown_path` существует, `len(references)==reference_stats.total`, пути фигур существуют. Не прошёл → повторный диспатч с тем же шаблоном; вторая неудача → зафиксируй блок и спроси пользователя.

### Фаза 1.5 — детерминированная быстрая оценка

```
python "${OPENCODE_HARNESS_ROOT}/scripts/paper-review/quick-assess.py" <markdown_path>
```
Сохрани JSON как `quick_assess.json`. Это вход для фокусировки субагентов и секция «Быстрая оценка» отчёта. НЕ редактируй вывод скрипта руками.

### Фаза 2 — параллельный диспатч (fan-out + merge, pattern из orchestration-patterns)

Все 3 субагента НЕЗАВИСИМЫ — вызовы `task` одним ходом (один ассистентский turn с несколькими task-вызовами), это даёт параллелизм.

**Общий для всех трёх prompt-скелет:**
```
Задача: <одно из: техническая рецензия / аудит ссылок / конкурентный анализ>.
Методология: ${OPENCODE_HARNESS_ROOT}/shared/paper-review-chain-contracts.md (<N>-й контракт).
Вход: ${PAPER_WORKSPACE}/analysis.json (+ quick_assess.json для фокусировки, venue-критерии).
Выход: запиши JSON-артефакт по контракту в ${PAPER_WORKSPACE}/<имя>.json.
Acceptance: <скопировать acceptance из контракта>. Не выдумывай SOTA-числа при недоступном API —
пометь в status_note. Один JSON-файл — единственный выход.
```

| Агент | Модуль контракта | Обязанности (коротко) |
|---|---|---|
| `technical-reviewer` | контракт 2, `tech_review.json` | формулы, эксперименты, статистика, SOTA, fairness |
| `reference-auditor` | контракт 3, `reference_audit.json` | верификация ссылок, недостающие цитаты, покрытие related work |
| `paper-comparator` | контракт 4, `competitor_analysis.json` | конкуренты за 12 мес, Tier 1-3, SOTA-позиция |

**Валидация контрактов 2–4** (после возврата, до сшивки): проверь acceptance каждого (скоупы score ∈ [1,5], severity enum, `verified+mismatch+not_found == total`, `tier1` непустой и т.д.). Нарушение → повторный диспатч этого субагента. Пропуск без исправления запрещён.

**Подожди все 3 возврата**: merge за один ход, частичный результат не сшиваешь. Если один субагент падает трижды — зафиксируй блок (tech_debt auto), продолжи с остальными, пометь в flags отчёта «агент X не выполнен, измерение Y оценено как n/a».

### Фаза 3 — merge (делаешь ТЫ, не субагент)

Собери `merged_scores.json` по детерминированным правилам из контракта 5:
1. 6 dimension_scores (4 из tech_review, related_work из reference_audit, competitiveness из competitor_analysis; writing/reproducibility — твоя оценки по `analysis.json` и `quick_assess.json`).
2. `overall_score` = среднее (1 знак).
3. Вердикт по порогам (≥4.5 accept, ≥3.8 weak_accept, ≥3.0 borderline, ≥2.2 weak_reject, <2.2 reject).
4. Критический триггер: любой `critical` → не выше `borderline`.
5. Флаги среды понижают confidence сшивки (−0.15 за флаг).

Затем заполни шаблон `Review_Report_<paper>.md` (из контракта 5) и покажи пользователю путь + краткую сводку: вердикт, overall score, critical/major/minor, недостающие базилайны, confidence.

### Опционально — `--with-code`

До сшивки (ультра-параллельно с Фазой 2, если даны права) прочитай код и добавь секции в отчёт: сверка формул с реализацией, нераскрытые приёмы, расхождения статья⇄код. Это делает оркестратор сам (или через `code-reviewer`, если он в контуре твоей сессии).

---

## Вспомогательные цепочки

### `/pre-screen` — быстрая предэкранная фильтрация (без полного цикла)

Не диспатчишь всех 4 субагентов. Только:
1. `paper-analyzer` → `analysis.json` (или прямое чтение через Read, если важно быстро).
2. `quick-assess.py` → `quick_assess.json`.
3. Форматируй отчёт `PreScreen_<paper>.md` из `quick_assess.json` (таблица сигналов + 1-2 предложения вывода + рекомендация, что смотреть при полном ревью).
4. Если задан `--venue` — сверь обязательный checklist мероприятия из venue-профилей.

Явно отметь в отчёте: «только поверхностные сигналы, содержание НЕ оценивалось».

### `/rebuttal` — анализ возражений/проверка ответов

Не диспатчишь субагентов цепочки (это не рецензирование). Работаешь сам:
- **Режим A (писать rebuttal):** прочитай `<review_file>`, структурируй по рецензентам (W/Q), классифицируй на 4 типа (прямой ответ / доп. эксперимент / правка / принципиальное), приоритизируй, черновик ответов.
- **Режим B (проверка исправлений):** прочитай `revised_pdf` (через `mcp__paper-parser__parse_paper` или Read), сопоставь с возражениями, статус ✅/⚠️/❌/ℹ️ на каждое, итоговый `Revision_Check_<paper>.md`.
- При необходимости уточнить статью (мод B) можно вызвать `paper-analyzer` для парсинга — но это опция, не обязательный шаг.

---

## Анти-паттерны оркестрации (не делай)

- **Субагент внутри субагента.** Цепочку ведёшь ты; `technical-reviewer` не вызывает `paper-comparator`.
- **Merge в чужом контексте.** Не диспатчь «синтезатор рецензии» субагентом — сшивка score по правилам контракта 5 делается в твоём контексте детерминированно. Отдельный merge-агент = потеря детерминизма.
- **Прогон Фазы 2 последовательно.** Три субагента независимы — вызывай в одном ходе.
- **Сшивка до валидации контрактов.** Некорректный JSON (score вне диапазона, невыполненный acceptance) — отклонение, а не «учтём как есть».
- **Субъективный вердикт в обход правил.** Вердикт из порогов; критический issue жёстко ограничивает. «В целом хорошо» вместо score — не сшиваемо.
- **Выдуманные SOTA-числа.** Недоступный API → `status_note` + флаг, не заполнение таблицы от балды.
- **Ручное редактирование `quick_assess.json`.** Детерминированный слой — не трогается.

## Завершение

1. Сохрани `Review_Report_<paper>.md` рядом с PDF (или в `${PAPER_WORKSPACE}` — скажи, куда положил).
2. Выдай: вердикт + overall score + критичные проблемы + недостающие базилайны + confidence + пути артефактов.
3. При блокировке — зафиксируй tech_debt через `tech_debt_cli.py auto` (см. `shared/harness-dispatch-map.md`).
4. Не возвращай содержимое всего отчёта — только сводку и путь.