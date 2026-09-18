# Writer Full Workflow Run — 2026-09-17

Статус: `EXECUTED / FULL CONTOUR VERIFIED / 2 TD FOUND`

## Схема (как просил) → реальные шаги

| # | Шаг схемы | Реальный CLI/модуль | Результат |
|---|---|---|---|
| 1 | Грубый черновик с данными и утверждениями | `wc_cli extract` (writer-core v2 hybrid) | 3 абзаца, 2 claims (GROUNDED), objects (CeO2/ZrO2, 10мкМ, IC50, 8.2мкМ, 2θ) |
| 2 | Стилистические шаблоны | `wc_cli register` (R1 референс/R2 вектор/R3 лексика/R4 тропы) | PASS, n_issues=0 |
| 3 | Извлечение графов | `wc_cli graphs` | graph_built=3, skipped=30 (data-limited: нет Run/AuthorProfile/citation-маркеров) |
| 4 | Разбивка на клаймы | `extract` claims + `build_claims` | CLM-W0 (состав→решётка), CLM-W1 (ингибирует hERG) |
| 5 | Эталон DOM нового документа | `wc_cli dom` (template+plan+claims+graphs) | PROD-001, 6 chapters, 2 claims, 1 graph, validation valid |
| 6 | Долг неопределённости утверждений | `wc_cli uncertainty` | status_map: PROVISIONAL 2, **research_requests=[] (TD-069!)** |
| 7 | Передача ресерчеру | research_requests → должен питать Researcher | **БЛОКИРОВАН TD-069** |

## Найденные недоделки

### TD-069 (high, NEW)
- DOM строит claims с `verification.verdict=SUPPORTED`, `confidence=0.8`,
  `uncertainty.level="assumed"`.
- `uncertainty_bridge._claim_level` возвращает "assumed" (не в low/medium/high)
  → ветка else → **PROVISIONAL БЕЗ research_request**.
- Итог: `research_requests=[]` — **долг не передаётся ресерчеру**.
- Это блокирует шаг 7 твоей схемы (передача ресерчеру для закрытия неопределённости).

### TD-068 (подтверждён, high)
- Числовые предикаты не извлекаются как claims (0 claims для «равен 5.41 А», «даёт a=5.27», «IC50=8.2»).

## Положительное
- plan (11 секций, G1/G2), draftcheck (PASS, RTT), register (PASS), dom (valid),
  vectorsim (0.999) — работают детерминированно.
- DOM эталон строится корректно (6 chapters из template dissertation).

## Артефакты (evidence/writer-workflow-20260917/)
- writer_plan.json, writer_extract.json, writer_graphs.json, writer_claims.json,
  writer_dom.yaml, writer_uncertainty.json

## Связь с трекером
- **TD-069** (new): uncertainty 'assumed' → research_requests пуст → передача ресерчеру сломана.
- **TD-068**: числовые claims не извлекаются.
- Оба блокируют полный closed-loop Writer→Researcher.