# Writer Scenarios Run — 2026-09-17

Статус: `ALL SCENARIOS EXECUTED / DETERMINISTIC`
Модель: не требуется (детерминированный слой, без LLM)

## Сценарии и результаты

| Сценарий | CLI | Результат | Примечание |
|---|---|---|---|
| Извлечение (claims+objects) | `extract` | 3 абзаца, claims 1+1+0, objects (CeO2/ZrO2, 10мкМ, IC50, 8.2мкМ) | v2 hybrid: claim GROUNDED для «связано с составом», «ингибирует hERG» |
| Связки графов | `graphs` | graph_built=3, skipped=30 | Пропущено 30 из-за отсутствия doc-level/registry-данных (Run/Operation, AuthorProfile, citation-маркеры) — ожидаемо для extract-only |
| RTT-дифф (черновик vs контракт) | `draftcheck` | **PASS**, defects=[], checked=2 | Оба утверждения контракта найдены, без запрещённых трансформаций |
| Стиль/регистр | `register` | **PASS**, n_issues=0 (R1/R2/R3=0) | Регистр чист |
| Векторное сходство | `vectorsim` | cosine=0.9993, delta_claims=0 | Родственные тексты, ожидаемо высоко |

## Ключевые находки

### TD-068 (подтверждён в v2-extractor)
- Числовые предикаты → **0 claims**:
  - «Параметр решётки CeO2 равен 5.41 А» → 0
  - «Для x=0.5 расчёт даёт a=5.27 А» → 0
  - «IC50 = 8.2 мкМ» → 0
- Извлекаются только глагольные формы («вызывает», «мы показали, что»).
- **Системно в обоих extractor'ах** (scripts/writer/extractor и writer-core/v2_extractor).
- Блокирует верификацию количественных утверждений через claims-цикл.

### graphs: 30/33 skipped (data-dependent, не баг)
- Пропущены G-графы, требующие: Run/Operation, AuthorProfile, citation-маркеров,
  revision/review, политик, doc-дерева. Для extract-only артефакта — ожидаемо.
- `graph_built=3` — базовые графы построены.

## Артефакты (C:\Temp\opencode\)
- writer_extract.json / writer_extract2.json — извлечение
- writer_graphs.json — графы
- writer_draftcheck.json — RTT PASS
- writer_register.json — стиль PASS
- writer_vectorsim.json — cosine 0.9993

## Связь с трекером
- TD-068 — подтверждён (числовые claims не извлекаются) — **требует фикса**.
- draftcheck/register/vectorsim — работают детерминированно, no defects.