---
name: writer-review
description: "Ревью и рецензирование научных произведений: ветвистое ревью L1/L2/L3 (микро/мезо/макро), сравнение черновика с DOM/эталонами/версиями черновиков, циклы с constrained repair и эскалацией на human. Для article-writer(контроль черновика) и writing-orchestrator(рецензия структуры/эталонов). Детерминированно, без LLM."
compatibility: opencode 1.15.10+
version: 0.1.0
---

# writer-review — ревью и рецензирование фабрики письма

Слой ревью поверх **writer-core**: детерминированная ветвистая проверка черновика
на трёх уровнях (**L1** микро, **L2** мезо, **L3** макро), с циклами
«ревью → constrained repair → повторное ревью» и эскалацией на человека при
несходимости. Ревью сравнивает черновик с:

- **контрактом** (writing_contract.json / документ-эталон v8): семантика через
  RTT-дифф（factory_process.draftcheck);
- **планом** (structure_plan.json, `plan --topic`): полнота слотов/gaps/порядок секций;
- **DOM** (dom.yaml, контракт прослеживаемости): цитатный гейт citation_trace
- **эталонами и версиями черновиков** (89-dim вектор `vectorsim` + консолидация
  версий v1-v12 `consolidate`)。

Этот скилл — то, что агент использует ПЕРЕД выдачей черновика: после цикла ревью
либо `final_verdict: PASS`（можно выдавать）, либо `escalation: true` — требуется
approval человека, никогда не «протаскивается» мимо.

## Что делает

`writer_core.review`（модуль: ${OPENCODE_HARNESS_ROOT}/scripts/writer-core/writer_core/review.py）:

детерминированные проверки（без LLM），fail-closed на уровне каждого тира:



```text
черновик.md
   ├── L1 (микро): proofreader — стиль/термины/повторы（t0_ru +
   │               реестры лингвистики: повторы, канцелярит, терминология
   │               (объекты v2), длина предложений > 30 слов)
   ├── L2 (мезо): editor — структура/полнота слотов/gaps
   │               (structure_annotator.classify_paragraph + plan ->
   │                GAP_OPEN / SECTION_MISSING / ORDER)
   └── L3 (макро): reviewer — RTT-семантика + traceability
                    (factory_process.draftcheck + citation_trace)
         ↓
   review_report.json (final_verdict + issues по уровням + rounds + escalation)
```

## Как запустить（review CLI）

PowerShell 5.1:

```powershell
$wc = Join-Path $env:WRITER_CORE_ROOT "wc_cli.py"
& $env:WRITER_PYTHON $wc review --draft draft.md --contract writing_contract.json --plan structure_plan.json --dom dom.yaml --max-iterations 3 --out review_report.json
```

POSIX:

```sh
"$WRITER_PYTHON" "$WRITER_CORE_ROOT/wc_cli.py" review \
    --draft draft.md --contract writing_contract.json \
    --plan structure_plan.json --dom dom.yaml \
    --max-iterations 3 --out review_report.json
```

`--contract` обязателен для текущего CLI. Поэтому обычная статья без переданного
или сгенерированного контракта не запускает ни `draftcheck`, ни `review`, а явно
сообщает, что deterministic RTT не выполнялся. `--plan` и `--dom` опциональны:
не передавай их, если соответствующих артефактов нет. Минимальный допустимый
запуск с контрактом — `--draft` + `--contract`; L2 без плана пропускается, а
traceability без DOM не запускается.

## Уровни L1/L2/L3

| Уровень | Роль | Проверяет | Severity |
|---|---|---|---|
| **L1** (микро) | proofreader | повторы слов（>= 3 в предложении）, канцелярит（клише/booster）, терминология（ABBR_AMBIGUOUS / ABBR_REEXPANDED）, длина предложений（> 30 слов） | MINOR |
| **L2** (мезо) | editor | против плана/DOM: `SECTION_MISSING`（отсутствует секция）, `GAP_OPEN`（слот не заполнен）, `ORDER`（нарушен порядок секций） | BLOCKER / INFO |
| **L3** (макро) | reviewer | RTT-дифф против контракта（defect_type + claim_id + span: causality_upgrade, modality_upgrade, claim_omission, ...） + traceability（citation_trace: orphan_claim, dangling_reference, masked_uncertainty, numeric_unverified, ...） | BLOCKER |

Вердикт уровня L3 — `PASS`|`FAIL`; общий вердикт цикла — **fail-closed**:
`FAIL`, если RTT FAIL / trace FAIL / есть L2-BLOCKER'ы / ошибка любого тира。

## Сравнение с эталонами и версиями

- **С эталоном**（документ-эталон v8 / референсная работа）: 89-dim вектор
  `graph_vector`（cosine_similarity + dynamic_metrics） — чем ближе вектор черновика
  к вектору эталона, тем ближе структура/аргументация:：
  PowerShell 5.1:
  ```powershell
  $wc = Join-Path $env:WRITER_CORE_ROOT "wc_cli.py"
  & $env:WRITER_PYTHON $wc vectorsim --a draft.json --b etalon.json --out vectorsim.json
  ```
  POSIX:
  ```sh
  "$WRITER_PYTHON" "$WRITER_CORE_ROOT/wc_cli.py" vectorsim --a draft.json --b etalon.json --out vectorsim.json
  ```
- **С версиями черновиков**（v1..v12）: `consolidate --versions-dir <dir>` — эволюция
  структуры/claims по версиям（evolution_report.json/.md; similarity между версиями）。
- **С DOM**（literary object）: L3-тир гоняет `citation_trace` против dom.yaml —
  каждое фактическое утверждение → claim → source+span; неопределённость явная。

## Циклы и эскалация

```text
draft → L1/L2/L3 (параллельно, threads) → вердикт
  ├── PASS  → approved (можно выдавать; конец)
  └── FAIL  → constrained repair (ТОЛЬКО по L3-дефектам:
              defect_type + claim_id + span; чужие spans не трогаются)
              → повторный прогон L1/L2/L3
              → максимум --max-iterations (по умолчанию 3)
              → остановка: iteration_limit | no_progress (ремонт не изменил текст)
              → escalation: true (human approval required)
```

Правила:
1. **Constrained repair** — только L3-дефекты с span（`apply_constrained_repair`）;
   дефекты без span（`claim_omission`）не репарируются детерминированно。
2. **Остановка** — `approved` / `iteration_limit` / `no_progress`; никогда бесконечный
   цикл.
3. **Эскалация** — если после цикла вердикт != PASS → `escalation: true` +
   `escalation_reasons`（семантические/структурные дефекты не устраняются
   детерминированным ремонтом → требуется approval человека）。

## Контракт выхода（review_report.json）

```json
{
  "schema": "writer_core.review_report.v1",
  "generated_by": "writer_core.review.REVIEW_CYCLE",
  "inputs": { "draft", "contract", "plan", "dom", "max_iterations", "draft_chars" },
  "iterations": 3,
  "final_verdict": "FAIL",
  "stopped_reason": "iteration_limit | approved | no_progress",
  "escalation": true,
  "escalation_reasons": ["..."],
  "issues_by_level": {
      "L1": [ { "level": "L1", "type": "REPETITION|LONG_SENTENCE|KANTSELLARIT|TERMINOLOGY", "span": [s,e], "text", "suggestion", "severity": "MINOR" } ],
      "L2": [ { "level": "L2", "type": "GAP_OPEN|SECTION_MISSING|ORDER", "slot_id", "section", "severity": "BLOCKER|INFO" } ],
      "L3": [ { "level": "L3", "type": "defect_type", "span", "text", "suggestion", "claim_id", "severity": "BLOCKER" } ]
  },
  "rtt_defects_final": [...],
  "trace_checks_final": { "verdict": "PASS|FAIL|error", "checks": { "dangling_reference", "orphan_claims", "masked_uncertainty", "numeric_unverified", "missing_crossref" } },
  "repaired_spans": [ { "claim_id", "defect_type", "start", "end" } ],
  "rounds": [ { "iteration", "verdict", "reasons", "n_l1", "n_l2", "n_l3_defects", "trace_verdict", "changed" } ]
}
```

Выход — детерминированный JSON（UTF-8）; любой сбой на битом вводе（нет
черновика / пустой контракт）→ `{"error": ..., "fail_closed": true}` + exit code 2.

## Fail-closed

1. Битый ввод → JSON-ошибка + ненулевой exit code（2）；исключения наружу не
   пробрасываются из CLI。
2. Ошибка ОТДЕЛЬНОГО тира внутри цикла → отчёт с `"error"` по тиру, цикл
   продолжается; общий вердикт при этом `FAIL`（LEVEL_ERROR）。
3. L2 не запускается без плана（`skipped: true`）— не выдумываем секции。
4. Constrained repair меняет только дефектные `claim_id + span`；чужие фрагменты
   не трогаются（проверяется тестом）。
5. Иттерации ограничены（`max_iterations`）; при отсутствии прогресса — `no_progress` stop。
6. FAIL после цикла → `escalation: true` — требуется approval человека, никогда
   не «протаскивается» мимо。

## Роли

- **article-writer**（worker, mode all）: прогоняет `review` ПЕРЕД выдачей черновика; выход —
  `review_report.json`; при `escalation: true` — передаёт на approval человеку。
- **writing-orchestrator**（primary, высший ранг）: рецензия структуры/эталонов —
  `review --plan`（L2-тир: полнота слотов/gaps против плана）+ `vectorsim`（сравнение
  с эталоном）и `consolidate`（версии v1-v12）。 Высший ранг: вердикт ревью —
  не право article-writer'а, а оркестратора/human。



## См. также

- `writer-core`（детерминированный слой: plan/draftcheck/dom/graphs/vector）。
- Контракт прослеживаемости: `${OPENCODE_HARNESS_ROOT}/shared/writer-traceability-contract.md`
- Цитатный гейт: `${OPENCODE_HARNESS_ROOT}/scripts/writer/citation_trace.py`

## Маркеры Windows (Windows Search & Extraction Markers)

Те же проблемы, что в `writer-core`: `.doc` не читается python-docx → используй
`writer_core` `doc_com` (`$doc.Content.Text`, НЕ `SaveAs` — «Ошибка метода»/method error);
`rg` нет → `Select-String -LiteralPath`; grep тянет общий temp →
сужай `path` до целевого; Python запускай только через переносимый
`WRITER_PYTHON` (PowerShell: `& $env:WRITER_PYTHON -X utf8`, POSIX:
`"$WRITER_PYTHON" -X utf8`);
большие файлы → `Read` чанками. Маркеры пиши на русском и английском.

После изменения этой harness-копии синхронизируй skill в live OpenCode config и
перезапусти OpenCode; live-копия не является источником истины.
