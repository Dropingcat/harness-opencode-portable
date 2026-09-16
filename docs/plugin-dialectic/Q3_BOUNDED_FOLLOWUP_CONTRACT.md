# Q3 Bounded Follow-up — Dialectic Control Contract

Status: `IMPLEMENTED / CANONICAL-DEFAULT PRESERVED / SEMANTIC-LEVEL COMPARISON NOT IMPLEMENTED`
Date: 2026-09-15
Source of truth: `scripts/researcher/researcher_core/tribunal_dialectic.py`
Reference architecture: `RESEARCHER_R4_4_DIALECTIC_OBSERVER_ARCHITECTURE.md` (§11–12)

## 1. Problem

После A2 (bounded cross-exam) пользовательский процесс допускает либо эскалацию до Q3,
либо прерывание — в зависимости от содержательного уровня Q3 по сравнению с Q2.
Текущий observer по умолчанию останавливается на L3 после двух пар Q/A.

Документ фиксирует решение: **Q3 — это явное, управляемое решение Core, а не дефолт.**
Новизна проблемы необходима, но не достаточна; лимиты глубины/пар/turn остаются.

## 2. Canonical default (не менялось)

- `max_level = L3_QUESTION_ON_ANSWER`
- `max_question_answer_pairs = 2`
- `require_novelty_for_followup = True`
- `escalate_blocking_discovery = True`

После A2 на L3 observer возвращает `STOP_DEPTH_LIMIT` (канон `test_tribunal_dialectic.py:174`).
Q3 по умолчанию не допускается.

## 3. Opt-in bounded follow-up

Новое поле `DialecticPolicy.allow_bounded_followup: bool = False`.

При `True` и одновременном выполнении всех условий observer в `decide_dialectic_control`
(в depth-ветке) возвращает:

```text
CONTINUE_QUESTION_ON_ANSWER
  level = L3_QUESTION_ON_ANSWER   (остаётся на том же уровне)
  reason_codes = ["BOUNDED_FOLLOWUP_QA_EXTENSION"]
```

Условия допуска:
1. `policy.allow_bounded_followup is True`;
2. `observation.level is policy.max_level` (текущий уровень равен максимуму);
3. `observation.qa_pair_count <= policy.max_question_answer_pairs` (слот пары свободен,
   т.е. политика должна поднять `max_question_answer_pairs` до 3);
4. есть **новые** проблемы (`issues` не пусто);
5. ни одна из них не блокирующая.

Новизна уже обеспечена более ранней проверкой
`require_novelty_for_followup` (STOP_NO_PROGRESS при отсутствии новизны).
Блокирующие проблемы не могут открыть Q3 (они ведут в эскалацию `REQUEST_LOCAL_RESEARCH`
или `RECOMPOSE_PANEL`).

## 4. Порядок правил в decide_dialectic_control

```text
1. escalate blocking discovery            -> L4 REQUEST_LOCAL_RESEARCH / RECOMPOSE_PANEL
2. issue fanout limit                     -> STOP_OPEN
3. all tracked issues resolved            -> STOP_CONVERGED
4. token budget                          -> STOP_BUDGET_LIMIT
5. turn limit                            -> STOP_TURN_LIMIT
6. no-progress streak                    -> STOP_NO_PROGRESS
7. novelty required (нет новизны)        -> STOP_NO_PROGRESS
8. level >= max_level:
     Q3-допуск (все условия выше)        -> CONTINUE_QUESTION_ON_ANSWER (L3)
     иначе                                -> STOP_DEPTH_LIMIT
9. position OPEN без проблем              -> STOP_OPEN
10. L0/L1/L2 ветки, затем L3              -> STOP_CONVERGED
```

Q3-допуск встроен в depth-ветку (п.8), поэтому он не может «обойти» лимиты
бюджета/turn/новизны и не переоткрывает L2.

## 5. Что проверено тестами

`tests/researcher/test_tribunal_dialectic.py` (17 passed):

| Тест | Policy | Результат |
|---|---|---|
| `test_q3_followup_is_denied_by_default_after_bounded_cross_exam` | default | `STOP_DEPTH_LIMIT` |
| `test_q3_followup_is_admitted_when_policy_permits_and_issue_is_new` | `allow_bounded_followup=True`, max_pairs=3 | `CONTINUE_QUESTION_ON_ANSWER` + `BOUNDED_FOLLOWUP_QA_EXTENSION` |
| `test_q3_followup_denied_for_repeated_issue` | `allow_bounded_followup=True`, max_pairs=3, повтор проблемы | `STOP_NO_PROGRESS` |

## 6. Что НЕ реализовано (явно)

**Сравнение «содержательного уровня Q3 по сравнению с Q2» автоматически не выполняется.**
Observer проверяет новизну как «новая проблема» (новая сигнатура), а не как
«более глубокая/содержательно иная грань вопроса». Это отдельный контракт
(содержательная мера глубины/фасета вопроса), требующий:

- либо typed issue facet/equivalence identity (см. TD-044);
- либо Hypothesis/ReviewFacet-level novelty (см. TD-047/048);
- либо live calibration (см. TD-042).

Пока это не реализовано, «эскалация до Q3 по уровню» означает только
опциональное расширение числа пар, разрешённое политикой, а не автоматическое
измерение семантической глубины Q3 относительно Q2.

## 7. Границы полномочий (не менялись)

- Решение о продолжении принимает **Core** (observer/policy). Плагин не выбирает.
- `CONTINUE_QUESTION_ON_ANSWER` — это control decision, не изменение truth.
- Плагин транспортирует уже принятый bounded semantic request.
- Данный документ — часть Host/Dialectic layer; Writer/Researcher/Coder state contracts не менялись.