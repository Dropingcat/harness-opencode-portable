---
name: writer-core
description: "Детерминированный слой фабрики письма: планирование структуры (G1/G2-слоты), semantic RTT draft-check, constrained repair, консолидация версий, DOM-контракт прослеживаемости (cli dom), дерево клаймов из 12 графов (graph_builder_hybrid), 89-dim вектор сравнения(graph_vector), ветвистое ревью L1/L2/L3 (cli review). Для writing-orchestrator(план/DOM/рецензия) и article-writer(контроль черновика против контракта/ревью)。Polza—только дешёвый guard/парсер."
compatibility: opencode 1.15.10+
version: 0.2.0
---

# writer-core — фабрика письма (детерминированный «компилятор»)

Писатель — двухуровневая фабрика: **writing-orchestrator** (планировщик,
ВЫСШИЙ ранг) + **article-writer** (воркер, mode: all). Этот скилл — то, что
находится ПОД обоими: детерминированный слой «контракты → слоты → draft →
semantic RTT → constrained repair → DOM → review». Здесь нет LLM-вызовов: весь слой —
реализация поверх модулей writer-core из HARNESS (`${OPENCODE_HARNESS_ROOT}/scripts/writer-core`).

| Роль | Ранг | Использование модуля |
|---|---|---|---|
| `writing-orchestrator` | primary, высший | **инструмент планирования и рецензии**: тема/ResearchBundle → структура будущего текста (секции, слоты, required_claims/artifacts, gaps) → «дерево для заполнения блоками» (plan) → DOM-каркас (dom) → рецензия структуры (review --plan); |
| `article-writer` | worker (all) | **инструмент контроля и ревью**: читает writing_contract.json, после черновика — claim re-extraction draft → RTT-дифф против разрешённых claims → constrained repair (дефект → claim_id → span); затем ветвистое ревью (review) против DOM/эталонов; |
| `polza` | вспомогательный тир | дешёвый guard/парсер терминов/формул, fail-closed. НЕ семантика, НЕ главный агент. Главный агент — opencode runtime (LLM-вызовы агента) |

## Расположение модуля

```
${OPENCODE_HARNESS_ROOT}/scripts/writer-core/
    wc_cli.py               # единый детерминированный CLI entry point (запуск из любого cwd)
    writer_core/
        __init__.py
        cli.py              # парсер команд (12 команд)
        contracts.py        # ResearchBundleLA, WriterContract, Defect, VersionedArtifact
        factory_process.py  # writer-цикл: draft -> RTT -> constrained repair
        live_cycle.py       # «живой» контур кодекра: bundle->claims->contract->draft->rtt->repair
        dom_builder.py      # связка writer_core с DOM-контрактом прослеживаемости (cli dom)
        review.py           # ветвистое ревью L1/L2/L3 с циклами и эскалацией (cli review)
        requirements-writer-core.txt
    v2_extractor/           # детерминированный + LLM-слой экстракции (c5_number, claim_qa, ...)
    structure_annotator.py  # G1/G2: документ-дерево, план, слоты
    hybrid_extract.py       # гибридный экстрактор (v2 + T0-digest)
    graph_builder_hybrid.py # графы G1-G16
    graph_vector.py         # 89-dim вектор
    consolidation.py        # консолидация версий
    rtt_compare.py, t0_ru.py, digest_builder.py, md_clean.py
    session_memory.py, polza_light.py, weak_llm.py, corpus_runner.py
```

Готовые модули импортируются (НЕ копируются): `hybrid_extract` + `md_clean`,
`graph_builder_hybrid`, `graph_vector`, `structure_annotator`, `consolidation`,
`rtt_compare` + `t0_ru` + `digest_builder`, `session_memory`, `polza_light`,
`citation_trace` (scripts/writer). Канонический venv: `E:\Documents\Документы\writer-core\.venv`
(Python 3.12.2). Env: `WRITER_CORE_ROOT` (по умолчанию `${OPENCODE_HARNESS_ROOT}/scripts/writer-core`),
`WRITER_RUNS_DIR` (bootstrap: `${OPENCODE_RUNS_DIR}/writer-core`) и
`WRITER_LINGUISTICS_REGISTRY_DIR` (bootstrap:
`${OPENCODE_HARNESS_ROOT}/scripts/writer_core_handoff/linguistics`).

## Workflow (plan → DOM → draft → draftcheck → repair → review)

```text
[тема/ResearchBundle]                [шаблон DOM YAML]         [writing_contract.json]
        │                                       │                            │
        ▼                                       ▼                            ▼
  1. plan (orchestrator)        2. dom (orchestrator)      черновик .md (article-writer)
      structure_plan.json                 DOM YAML: structure от           │
      (G1-дерево + G2-слоты +          plan + claims + графы +          ▼
       gaps)                             uncertainty по происхождению   3. draftcheck (детерминированный слой)
      «дерево для заполнения              (контракт traceability)      re-extraction draft (hybrid_extract)
       блоками»                                  │                       + RTT-дифф против contract-claims
        │                                        ▼                              │
        └───────────►  DOM-каркас  ←── гейт «нельзя выдать»:    PASS ── approve ──► конец
                          (document.yaml)    citation_trace.py (exit 0|1|2)    FAIL ──► 4. constrained repair
                                                                               (дефект → claim_id → span, ТОЛЬКО
                                                                                дефектные фрагменты; чужие spans
                                                                                не модифицируются)
                                                                               → повтор draftcheck
                                                                               → иттерации ограничены (max 3)
                                                                               → 5. review (ветвистое ревью L1/L2/L3)
                                                                                 → эскалация на human при FAIL
```

## Traceability и DOM (иерархия истины)

Контракт прослеживаемости — `${OPENCODE_HARNESS_ROOT}/shared/writer-traceability-contract.md`
(WS-18).

 Иерархия истины:

```
DOM YAML (источник истины: structure + claims + graphs + traceability + uncertainty)
   ↓
Готовый текст (один из многих выходов; прослеживаемость в тексте = `[Sxx]`/`[Cxx]` ссылки)
```

Правила:
1. Writer пишет текст, но НЕ выдумывает факты — каждый фактический клайм уже есть в DOM。
  Если в прозе появилось утверждение, которого нет в DOM — это ошибка. Writer обязан
  сначала добавить claim в DOM (с источником), потом писать。
2. Если DOM-claim не подтверждён (UNSUPPORTED/OPEN) — в тексте это маркируется
  неопределённостью, а не подаётся как факт。
3. Гейт «нельзя выдать» — детерминированный скрипт
  `${OPENCODE_HARNESS_ROOT}/scripts/writer/citation_trace.py`:
  `python citation_trace.py --text draft.md --dom <slug>-dom.yaml [--strict]`
  exit 0 = PASS (можно выдавать), exit 1 = FAIL (править и перезапускать). Проверки:
  `orphan_claim`, `dangling_claim`/`dangling_source`, `masked_uncertainty`,
  `numeric_unverified`, `dangling_section`, `missing_crossref` (warn).
4. Writer НЕ ведёт верификацию сам — он **потребляет** её из DOM
  (`claims[].verification.verdict` приходит из fact-checker; `numeric_comparison` — из numeric_comparator)。

## DOM YAML: как создать

DOM YAML — литературный объект (product/structure/claims/graphs/uncertainty/sources）。
Создаётся из нашего слоя детерминированно:

```bash
# Шаблон DOM (литературный объект) — выбор после постановки задачи:
#   ${OPENCODE_HARNESS_ROOT}/templates/writer-dom-dissertation.yaml

# Каркас структуры (11 секций автореферата -> главы диссертации):
$WCPY $WC plan --topic "Тема диссертации" --out structure_plan.json

# Собрать DOM: structure из plan + claims из hybrid_extract/bundle + графы G3-G15
#   + uncertainty ПО ПРОИСХОЖДЕНИЮ источников (--source-kind повторяемый):
$WCPY $WC dom --template "${OPENCODE_HARNESS_ROOT}/templates/writer-dom-dissertation.yaml" \
    --plan structure_plan.json \
    --claims claims.json \        # list[claim] | {"claims": [...]} | ResearchBundleLA.json
    --graphs graphs.json \          # CLI graphs ИЛИ вывод build_paragraph_graphs
    --source-kind raw_data --source-kind published \
    --out dom.yaml
```

Формат `document.yaml` (контракт, иерархия DOM→проза):

```yaml
product: { id: PROD-001, kind: dissertation|monograph|textbook|paper, title, status }
structure:                          # базовая структура из шаблона/plan
  chapters:
    - id: CH-01
      sections:
        - id: SEC-01-01
          paragraphs:
            - id: PAR-01-01-01
              claims: [C-001, C-002]   # какие клаймы параграф выражает
              expected: RESULT_CLAIM      # слот плана (claim_id-ожидание от research)
              slot_id: CS_RESULTS_RESULT_CLAIM
              text: ""                    # заполняется черновиком
claims:                                # реестр утверждений (id: C-001.., kind, verification)
  - id: C-001
    text: "..."
    kind: factual|derived|assumed
    evidence: [ { source_id: S-012, span: "p.47, §3.2: «...»" } ]
    verification: { verdict: SUPPORTED|CONTRADICTED|UNSUPPORTED|AMBIGUOUS|OPEN, confidence: 0.8 }
graphs:                                # графы связей (kind: support|derivation|conflict|citation_chain)
  - id: GRAPH-01
    edges: [ { from: C-001, to: C-002, relation: derived_from|supports|contradicts|depends_on } ]
uncertainty:                          # неопределённость — первичное поле
  C-001: { level: established|inferred|assumed|disputed, note: "..." }
sources:                              # реестр источников
  - id: S-012
    ref: "Author. Title. Journal, year, p.47"
    kind: primary|secondary
```

Связь слотов с claim_id: `structure[].paragraphs[].claims[]` содержит `claim_id` реестра;
`expected`/`slot_id` — слот плана, который research должен заполнить утверждением.

Неопределённость ПО ПРОИСХОЖДЕНИЮ (шкала из dom_builder, deterministic):

| `--source-kind` | level |
|---|---|
| `raw_data` / `эксперимент` / `черновик первичных данных` | `high` |
| `published` / `автореферат` / `защищённая диссертация` / `статья` | `low` |
| `direct_method` | `low` |
| `indirect_method` | `medium` |
| `modeling` | `medium-high` |
| `hypothesis` | `high` |
| (неизвестное) | `medium` |

## 12 графов и вектор (дерево клаймов)

`graph_builder_hybrid` строит графы реестра из артефакта документа: G1-G16
(12+ графов; **G4** аргументация (CONCLUDES→derivation), **G5** эпистемика
(DERIVED_FROM/SUPPORTS/PARTIALLY_SUPPORTS/CONTRADICTS→derivation/support/conflict),**G6** артефакты
(DERIVED_FROM→derivation), **G14** кохезия/информационный поток (REFERS_TO/COREFERS_WITH→citation_chain)；
G7 цитатное происхождение, G8 политика/ограничения, G9 зависимости ревизий,

```bash
# Построить графы из артефакта (G1-G16) + опционально в sqlite:
$WCPY $WC graphs --artifact artifact.json --out graphs.json --sqlite graphs.db

# 89-dim вектор для сравнения（cosine + dynamic_metrics: схема — G*_n/G*_e/G*_ratio,
#   LOO 79% по разбору версий v1-v12)：
$WCPY $WC vectorsim --a old.json --b new.json --out vectorsim.json
```

Работа с деревом клаймов:
- **G4/G5/G6/G14** маппятся в DOM `graphs[]` при `cli dom --graphs`（kind:
  support/derivation/conflict/citation_chain, edges: from/to/relation）。
- **Вектор 89-dim** — для сравнения версий/эталонов: `cosine_similarity` + `dynamic_metrics`
  (количество графов/рёбер по типам). Чем ближе вектор черновика к вектору эталона —
  тем ближе структура/аргументация。 Сравнение версий: `cli consolidate` (v1..v12) + `vectorsim`.

## Ревью и рецензирование（L1/L2/L3)

Ветвистое ревью — `cli review`（детерминированно, без LLM）：

```text
черновик.md
   ├── L1 (микро): proofreader — стиль/термины/повторы (t0_ru + реестры
   │               лингвистики: повторы, канцелярит, терминология (объекты v2),
   │               длина предложений > 30 слов)
   ├── L2 (мезо): editor — структура/полнота слотов/gaps
   │               (structure_annotator.classify_paragraph + plan -> GAP_OPEN /
   │                SECTION_MISSING / ORDER)
   └── L3 (макро): reviewer — RTT-семантика + traceability
                    (factory_process.draftcheck + citation_trace)
         ↓
   review_report.json (final_verdict + issues по уровням + rounds + escalation)
```

```bash
# Ревью черновика против контракта+плана+DOM（L1+L2+L3 параллельно， циклы max 3）：
$WCPY $WC review --draft draft.md \
    --contract writing_contract.json \    # ИЛИ документ-эталон (v8, docx/pdf/md) ИЛИ inline-JSON
    --plan structure_plan.json \          # для L2-тира (структура/слоты/gaps）
    --dom dom.yaml \                      # для L3-цитатного гейта（citation_trace）
    --max-iterations 3 \
    --out review_report.json
```

- **Циклы**: при FAIL → constrained repair (ТОЛЬКО по L3-дефектам: defect_type + span) →
  повторный прогон L1/L2/L3 → максимум `--max-iterations` (по умолчанию 3);
  остановка: `approved` (PASS), `iteration_limit`, `no_progress` (ремонт не изменил текст).

- **Эскалация на human**: если после цикла вердикт != PASS → `escalation: true`
  + `escalation_reasons` — semantic/структурные дефекты не устраняются детерминированным
  constrained repair → требуется approval человека。
- **Сравнение с эталоном и версиями**: `vectorsim --a черновик.json --b эталон.json`
  (89-dim cosine/dynamic_metrics; версии v1-v12 — через `consolidate --versions-dir`,
  эволюция структуры/claims по версиям)。

## Команды CLI (12 команд）

```bash
WCPY="${PYTHON}"
WC="${WRITER_CORE_ROOT}/wc_cli.py"
# Любой cwd. ENV: WRITER_CORE_ROOT (по умолчанию scripts/writer-core), WRITER_RUNS_DIR.

# 1) plan — структурный план будущего текста (G1-дерево + G2-слоты + gaps）:
#   --doc <образец> | --bundle <ResearchBundleLA.json> | --topic "<тема>" (каркас БЕЗ документа)
$WCPY $WC plan --topic "Тема диссертации" --out structure_plan.json
$WCPY $WC plan --bundle bundle.json --out structure_plan.json

# 2) draftcheck — RTT-дифф черновика против контракта（
$WCPY $WC draftcheck --draft draft.md --contract writing_contract.json --out rtt_report.json

# 3) live-cycle — полный контур кодекра（bundle->contract->draft->rtt->repair）：
$WCPY $WC live-cycle --bundle bundle.json --contract writing_contract.json \
    --draft draft.md --repair --out live_cycle_report.json

# 4) extract — гибридная экстракция документа -> artifact.json
$WCPY $WC extract --doc paper.docx --out artifact.json

# 5) graphs — графы реестра G1-G16 из artifact.json (+ --sqlite .db)
$WCPY $WC graphs --artifact artifact.json --out graphs.json --sqlite graphs.db

# 6) annotate — разметка структуры документа -> structure_plan.json
$WCPY $WC annotate --doc paper.docx --out structure_plan.json

# 7) consolidate — консолидация версий (v1..v12) -> evolution_report.json/.md
$WCPY $WC consolidate --versions-dir "F:\1\_STRUCTURED\07_AUTOREF\versions" \
    --out-dir evolution

# 8) vectorsim — 89-dim cosine + dynamic_metrics двух артефактов
$WCPY $WC vectorsim --a old.json --b new.json --out vectorsim.json

# 9) dom — writer_core -> DOM YAML по контракту прослеживаемости (для citation_trace.py)
$WCPY $WC dom --template "${OPENCODE_HARNESS_ROOT}/templates/writer-dom-dissertation.yaml" \
    --plan structure_plan.json --claims claims.json --graphs graphs.json \
    --source-kind raw_data --source-kind published --out dom.yaml

# 10) review — ветвистое ревью（L1 микро + L2 мезо + L3 макро， циклы， эскалация）
$WCPY $WC review --draft draft.md --contract writing_contract.json \
    --plan structure_plan.json --dom dom.yaml --max-iterations 3 --out review_report.json
```

Выход — детерминированный JSON; любой сбой на битом вводе — `{"error": ...,
"fail_closed": true}` и exit code 2。

## Контракты

- **ResearchBundleLA** — `task_contract`, `sources[]`, `claims[]`,
  `evidence_links[]`, `contradictions[]`, `unresolved_questions[]`,
  `confidence_map` (строится из claims/objects гибрида, маппинг
  `research_bundle_from_artifact`).
- **WriterContract** — `claim_id`, `proposition`, `scope`, `modality`,
  `causal_level`, `forbidden_transformations`, `required_qualifiers`,
  `citation_policy` (маппится из LinguisticDigest/claims,
  `writer_contract_from_claim`).
- **Defect** — `defect_type` (snake_case RTT-причины: `causality_upgrade`,
  `modality_upgrade`, `scope_expansion`, `numeric_drift`, ...), `claim_id`,
  `span` (абсолютные координаты в черновике), `suggestion` (вход constrained
  repair).
- **VersionedArtifact** — `id`, `version`, `content_hash` (sha256 от
  содержимого, считается функцией, не принимается извне), `created_at`。
- **DOM YAML** (литературный объект, контракт прослеживаемости:
 `product` / `structure` (chapters→sections→paragraphs, `claims[]` — claim_id,
 `expected`/`slot_id` — слот плана) / `claims[]` (id C-xxx, `kind`, `evidence`,
 `verification.verdict`) / `graphs[]` (kind: support|derivation|conflict|citation_chain) /
 `uncertainty{}` (level по происхождению) / `sources[]` (id S-xxx, `ref`, `kind`)。

## Что от тебя ждут (контракты входа/выхода)

- **writing-orchestrator** (primary, высший ранг):
  вход — тема/ResearchBundle/шаблон DOM; выход — `structure_plan.json`（plan）,
  `dom.yaml`（dom-каркас + uncertainty） и `review_report.json` (рецензия структуры,
  `review --plan` — L2-тир: полнота слотов/gaps против плана).
  Ты НЕ пишешь прозу—ты строишь «дерево для заполнения блоками» и контролируешь прослеживаемость。
- **article-writer** (worker, mode all:
  вход — `writing_contract.json`/эталон (v8) + черновик .md; выход — `rtt_report.json`
  （draftcheck） и `review_report.json`（review: L1/L2/L3 против контракта/DOM/плана）.
 Ты пишешь прозу только из claims DOM, маркируешь неопределённость, чинишь дефекты
  constrained repair'ом （дефект → claim_id → span）。
- **polza** — только дешёвый guard/парсер терминов/формул, fail-closed; её вывод НЕ
  используется для семантических решений этого слоя。
- **Выход детерминирован**: JSON + exit code; никакой LLM-интерпретации на стороне кода。



## Fail-closed принципы

1. LLM свидетельствует, **детерминированный слой решает**: все проверки
   (re-extraction, RTT-дифф, ремонт, ревью L1/L2/L3, DOM-гейт) — код, не LLM。
2. Битый ввод → JSON-ошибка + ненулевой exit code (2); исключения наружу не
   пробрасываются из CLI。
3. Constrained repair меняет **только** дефектные `claim_id + span`; чужие
   фрагменты не трогаются (проверяется тестом)。
4. Иттерации цикла ограничены (`max_iterations`); при отсутствии прогресса —
   `no_progress` stop, никогда бесконечный цикл。
5. Polza — только дешёвый guard/парсер (термины/формулы, fail-closed); её
   вывод НЕ используется для семантических решений этого слоя。
6. Гейт «нельзя выдать» — детерминированный `citation_trace.py` (exit 0 = PASS);
   проверяет claims/источники/неопределённость/числа/секции в тексте против DOM。
7. Ревью FAIL после цикла → `escalation: true` — требуется approval человека, никогда
   не «протаскивается» мимо человека。

## Канон данных и знаний (canon_data / canon_knowledge)

**Разделение канона** (модуль `writer_core.canon`): article-writer получает НЕ кашу
«канон», а два явных контракта:

```text
canon_data (данные — ЧТО НЕЛЬЗЯ МЕНЯТЬ)
  ├── data_entries[]: числа+единицы по claims (16 ч, 540°C, 6 мкм...)
  ├── numeric_compare[]: вердикты researcher (MATCH/MISMATCH/...)
  ├── formulas[]: formula_name + constant_check
  └── sources[]: реестр источников (DOI)
canon_knowledge (знания — ЧТО МОЖНО ПИСАТЬ И КАК)
  ├── claims[]: id, text, kind, verdict, confidence, level
  ├── readiness: READY (писать твёрдо) | PROVISIONAL (только tentative_only)
  ├── hedges{claim_id}: разрешённая хедж-фраза для PROVISIONAL
  └── research_requests[]: что запросить у researcher для понижения uncertainty
```

Правила:
1. Числа/единицы/формулы из `canon_data` — НЕ выдумывать, НЕ менять; проза не
   противоречит `numeric_compare`.
2. Утверждения — ТОЛЬКО из `canon_knowledge.claims`; PROVISIONAL — с хеджом из
   `hedges[]` в ТОМ ЖЕ предложении (иначе гейт `masked_uncertainty`).
3. Сводка для брифа: `writer_core.canon_brief(dom)` -> {canon_data, canon_knowledge}.

## Контроль научного регистра (register_control)

Модуль `writer_core.register_control` — 4 оси контроля прозы (детерминированно):
- **R1 РЕФЕРЕНС**: числа без [C-xxx]/[S-xxx] в предложении -> NUMERIC_ORPHAN (BLOCKER)
- **R2 РЕГИСТР**: 89-dim сходство секции с эталоном (канон v20) -> дрейф стиля
- **R3 ЛЕКСИКА**: kantseliarit_ratio vs норма 0.10, разговорные маркеры
- **R4 ТРОПЫ**: публицистические фигуры -> заменить на сухую научную прозу

```bash
$WCPY $WC register --draft draft.md --dom dom.yaml --out register_report.json
```

## Канбан-отчёт (ритуал закрытия, универсальный с секциями)

| Контур | group_name | agent_id (СВОЙ, не единый) |
|---|---|---|
| код | `code-factory` | code-orchestrator, coder-worker, ... |
| писатель | `writing` | writing-orchestrator, article-writer |
| ресёрчер | `research` | research-orchestrator, claim-parser, fact-checker, ... |

Отчёт — **канонический хелпер** (резолвит секцию по agent_id, регистрирует агента):

```bash
"${PYTHON}" "${OPENCODE_HARNESS_ROOT}/scripts/orchestration/kanban_report.py" report writing-orchestrator <task_id> <status> [phase] [progress] [message]
"${PYTHON}" "${OPENCODE_HARNESS_ROOT}/scripts/orchestration/kanban_report.py" board [group]    # доска по секциям
"${PYTHON}" "${OPENCODE_HARNESS_ROOT}/scripts/orchestration/kanban_report.py"                  # сводка
```

> ВАЖНО: старая сигнатура `gk.report(agent, task_id, task_name, status, phase, progress, msg)`
> НЕВЕРНА (позиционные аргументы не совпадают с реальной
> `report(agent_id, task_name, status, progress, message, task_id, phase)`) — не используй.
> Остаток нити: `project_context.py` → поле `kanban.rows[].group_name`.

## Поиск и извлечение — маркеры Windows (Search & Extraction Markers)

Проблемы, найденные в живых сессиях писателя на Windows (PowerShell 5.1), и их решения.
Маркеры дублируются на русском и английском — пиши в обоих вариантах, когда ссылаешься на них.

| Проблема (RU / EN) | Маркер (RU / EN) | Решение |
|---|---|---|
| `.doc` не читается python-docx / `.doc` unsupported by python-docx | `.doc` через Word COM / use Word COM `Content.Text` | `$WCPY $WC extract --doc <file.doc>` (модуль `doc_com.py`, win32com). НЕ `SaveAs` — «Ошибка метода»/"method error" (нестабилен в PS 5.1 COM); бери `$doc.Content.Text` напрямую. |
| `rg` нет / `rg` is not installed | искать без rg / search without rg | `Select-String -LiteralPath "<файл>" -Pattern "<regex>"` (принимает `-LiteralPath`, не тянет temp). |
| grep тянет temp-файлы / grep picks up temp files | ограничь поиск целевым каталогом / limit search to target dir | Передавай `path` строго целевой (литобзор/автореферат/`chunks/`), не общий временный каталог. |
| системный python без зависимостей / system python missing deps | venv обязателен / use venv | Всегда `$PY = E:\Documents\Документы\writer-core\.venv\Scripts\python.exe` (+ `-X utf8`). Системный python 3.11 падает на `project_context.py`. |
| кириллица в консоли (mojibake) / Cyrillic mojibake in console | `-X utf8` + `PYTHONIOENCODING` | Запускай `python -X utf8`; `$env:PYTHONIOENCODING="utf-8"` для вывода. ps1-файлы — ASCII-only или с BOM (PS 5.1 читает в cp866). |
| большие файлы рвут Read / large files break Read | читай чанками / read in chunks | `Read offset/limit` по кускам; временные чанки храни в `${WRITER_RUNS_DIR}/chunks/`. |
| Markitdown нет / markitdown missing | используй doc_com / use doc_com | `.doc`/`.docx` — через наш `doc_com.py` (Word COM), не markitdown. |
| grep-маркеры в .md / grep markers in .md | ищи в целевых файлах / search target files only | Греп по `*.md` тянет `cf_process.txt`/`corpus.txt` — сужай `include` до `*.md` в целевой папке. |

Быстрая проверка окружения (environment probe):

```powershell
$PY -c "import win32com, razdel, pymorphy3, yaml, docx; print('ENV_OK')"
```

Если `win32com` нет — `pip install pywin32`; если `razdel`/`pymorphy3` нет — см.
`writer_core\requirements-writer-core.txt`。



## H-память（session_memory）

Кросс-сессионные выводы писателя сохраняются в
`${WRITER_RUNS_DIR}/session_memory.json` (модуль `session_memory`,
схема `writer_verify.session_memory.v1`): `add_entry(секция, value)` /
`get(секция)`. Секции-примеры: `plan_etalon`, `known_pitfalls`,
`rtt_thresholds`, `review_etalon_vectors`. Перед тяжёлой диагностикой — читай память; после новых
находок — дописывай запись дня（append-only история по датам。



## Проверка

```bash
# py_compile всех модулей writer_core（fail-closed синтаксис）：
$PY -m py_compile writer_core\cli.py writer_core\dom_builder.py writer_core\review.py \
    writer_core\live_cycle.py writer_core\contracts.py writer_core\factory_process.py

# CLI help показывает dom/review/live-cycle/plan/draftcheck...:
$WCPY $WC --help

# pytest (полный harness）：
$WCPY -m pytest %OPENCODE_HARNESS_ROOT%\scripts\writer_core_handoff\tests\test_writer_harness.py -q (или целевой тест из scripts/writer-core/tests)
```

После изменения этой harness-копии синхронизируй skill в live OpenCode config и
перезапусти OpenCode; live-копия не является источником истины.

Покрытие: CLI plan (>= 8 секций + слоты), CLI draftcheck ловит дрейф
(defect `causality_upgrade` + claim_id + span), контракты валидны,
factory_process ограничивает иттерации, constrained repair не трогает чужие
spans, VersionedArtifact хэш, ResearchBundle маппинг, fail-closed на битый
ввод, DOM-гейт citation_trace (exit 0|1|2), ревью L1/L2/L3 с циклами/эскалацией。
