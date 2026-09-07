---
name: writer-core
description: "Детерминированный слой фабрики письма: планирование структуры (G1/G2-слоты), semantic RTT draft-check, constrained repair, консолидация версий. Для writing-orchestrator (план/структура будущего текста) и article-writer (контроль черновика против контракта). Polza — только дешёвый guard/парсер."
compatibility: opencode 1.15.10+
version: 0.1.0
---

# writer-core — фабрика письма (детерминированный «компилятор»)

Писатель — двухуровневая фабрика: **writing-orchestrator** (планировщик,
ВЫСШИЙ ранг) + **article-writer** (воркер, mode: all). Этот скилл — то, что
находится ПОД обоими: детерминированный слой «контракты → слоты → draft →
semantic RTT → constrained repair». Здесь нет LLM-вызовов: весь слой —
реализация поверх готовых модулей writer-гибрида.

| Роль | Ранг | Использование модуля |
|---|---|---|
| `writing-orchestrator` | primary, высший | **инструмент планирования**: тема/ResearchBundle → структура будущего текста (секции, слоты, required_claims/artifacts, gaps) → «дерево для заполнения блоками» |
| `article-writer` | worker (all) | **инструмент контроля**: читает writing_contract.json, после черновика — claim re-extraction draft → RTT-дифф против разрешённых claims → constrained repair (дефект → claim_id → span) |
| `polza` | вспомогательный тир | дешёвый guard/парсер терминов/формул, fail-closed. НЕ семантика, НЕ главный агент. Главный агент — opencode runtime (LLM-вызовы агента) |

## Расположение модуля

```
C:\Temp\opencode\writer_verify\hybrid\writer_core\
    __init__.py
    cli.py                  # единый детерминированный CLI (7 команд)
    contracts.py            # ResearchBundleLA, WriterContract, Defect, VersionedArtifact
    factory_process.py      # writer-цикл: draft -> RTT -> constrained repair
    requirements-writer-core.txt
```

Готовые модули импортируются (НЕ копируются): `hybrid_extract` + `md_clean`,
`graph_builder_hybrid`, `graph_vector`, `structure_annotator`, `consolidation`,
`rtt_compare` + `t0_ru` + `digest_builder`, `session_memory`, `polza_light`.
Канонический venv: `E:\Documents\Документы\writer-core\.venv` (Python 3.12.2).

## Workflow (plan → draft → draftcheck → repair)

```text
[тема/ResearchBundle]                 [writing_contract.json]
        │                                       │
        ▼                                       ▼
  1. plan (orchestrator)          черновик .md (article-writer)
     structure_plan.json                │
     (G1-дерево + G2-слоты +            ▼
      gaps) ───────────────────► 2. draftcheck (детерминированный слой)
     «дерево для заполнения         re-extraction draft (hybrid_extract)
      блоками»                      + RTT-дифф против contract-claims
                                           │
                              PASS ── approve ──► конец
                              FAIL ──► 3. constrained repair
                                       (дефект → claim_id → span, ТОЛЬКО
                                        дефектные фрагменты; чужие spans
                                        не модифицируются)
                                       → повтор draftcheck
                                       → иттерации ограничены (max 3)
```

## Команды CLI

```bash
PY=E:\Documents\Документы\writer-core\.venv\Scripts\python.exe
cd C:\Temp\opencode\writer_verify\hybrid

# 1) Планирование (orchestrator): структура будущего текста по образцу-документу
$PY -m writer_core.cli plan --doc "F:\1\_STRUCTURED\07_AUTOREF\versions\Автореферат_v8_АКТУАЛЬНАЯ.docx" --out structure_plan.json
#   или по ResearchBundleLA (без выдумывания секций — только данные бандла):
$PY -m writer_core.cli plan --bundle bundle.json --out structure_plan.json

# 2) Контроль черновика (article-writer): RTT-дифф против контракта
$PY -m writer_core.cli draftcheck --draft draft.md --contract writing_contract.json --out rtt_report.json
#   rtt_report.json: verdict PASS|FAIL, defects[{defect, claim_id, span, suggestion}]

# 3) Прочие команды
$PY -m writer_core.cli extract   --doc paper.docx --out artifact.json
$PY -m writer_core.cli graphs    --artifact artifact.json --out graphs.json --sqlite graphs.db
$PY -m writer_core.cli annotate  --doc paper.docx --out structure_plan.json
$PY -m writer_core.cli consolidate --versions-dir "F:\1\_STRUCTURED\07_AUTOREF\versions" --out-dir evolution
$PY -m writer_core.cli vectorsim --a old.json --b new.json --out vectorsim.json
```

Выход — детерминированный JSON; любой сбой на битом вводе — `{"error": ...,
"fail_closed": true}` и exit code 2.

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
  содержимого, считается функцией, не принимается извне), `created_at`.

## Fail-closed принципы

1. LLM свидетельствует, **детерминированный слой решает**: все проверки
   (re-extraction, RTT-дифф, ремонт) — код, не LLM.
2. Битый ввод → JSON-ошибка + ненулевой exit code; исключения наружу не
   пробрасываются из CLI.
3. Constrained repair меняет **только** дефектные `claim_id + span`; чужие
   фрагменты не трогаются (проверяется тестом).
4. Иттерации цикла ограничены (`max_iterations`); при отсутствии прогресса —
   `no_progress` stop, никогда бесконечный цикл.
5. Polza — только дешёвый guard/парсер (термины/формулы, fail-closed); её
   вывод НЕ используется для семантических решений этого слоя.

## H-память (session_memory)

Кросс-сессионные выводы писателя сохраняются в
`C:\Temp\opencode\writer_verify\session_memory.json` (модуль `session_memory`,
схема `writer_verify.session_memory.v1`): `add_entry(секция, value)` /
`get(секция)`. Секции-примеры: `plan_etalon`, `known_pitfalls`,
`rtt_thresholds`. Перед тяжёлой диагностикой — читай память; после новых
находок — дописывай запись дня (append-only история по датам).

## Проверка

```bash
$PY -m pytest C:\Temp\opencode\writer_verify\test_writer_harness.py -q
```

Покрытие: CLI plan (>= 8 секций + слоты), CLI draftcheck ловит дрейф
(defect `causality_upgrade` + claim_id + span), контракты валидны,
factory_process ограничивает иттерации, constrained repair не трогает чужие
spans, VersionedArtifact хэш, ResearchBundle маппинг, fail-closed на битый
ввод.