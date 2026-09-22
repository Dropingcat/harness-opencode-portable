---
name: triz-critic
version: 1.0.0
description: >
  Навык Критика ТРИЗ-агента. Проверяет выход Генератора по чек-листу
  из 6 пунктов: полнота покрытия, согласованность фактов,
  разнонаправленность концепций, конкретность источников,
  корректность приёмов ТРИЗ, реалистичность оценок.
agent: ТРИЗ-агент
inputs:
  - name: task_id
    type: string
    description: ID задачи
  - name: task_query
    type: string
    description: Запрос задачи
  - name: context
    type: dict
    description: Контекст задачи
  - name: iteration
    type: int
    description: Номер итерации
  - name: mode
    type: string
    description: Режим работы (sufficiency/optimality)
  - name: generator_output
    type: dict
    description: JSON-выход Генератора
outputs:
  - name: critic_report
    type: CriticReport
    description: Отчёт Критика с замечаниями и оценками
dependencies:
  - memory (встроенные данные)
  - resilience (retry, circuit_breaker)
  - metrics (MetricsLogger)
---

# Навык Критика (triz-critic)

## Описание

Критик проверяет решения, сгенерированные Генератором (Аналитиком и Дизайнером),
на соответствие методологии ТРИЗ, полноту и реалистичность.

## Чек-лист (6 пунктов)

| ID | Пункт | Описание |
|----|-------|----------|
| domain_coverage | Полнота покрытия | Все ли аспекты предметной области учтены? |
| fact_concept_consistency | Согласованность фактов | Концепции ссылаются на факты? |
| concept_diversity | Разнонаправленность | Концепции действительно разные? |
| source_specificity | Конкретность источников | Есть ли DOI/URL? |
| triz_correctness | Корректность ТРИЗ | Номера приёмов валидны? |
| estimates_realism | Реалистичность оценок | Оценки в разумных пределах? |

## API

### critique_generator_output(critic_input, llm_call, logger, tokens_callback, mode_config) -> CriticReport

Основной вход. Принимает CriticInput, вызывает LLM и возвращает CriticReport.

### build_critic_input(task_id, task_query, context, iteration, mode, generator_output, skip_checks) -> CriticInput

Хелпер для сборки CriticInput из выхода Генератора.

### validate_critic_output(raw_text) -> CriticReport | None

Парсинг и валидация сырого JSON из LLM.

## Режим работы

- **sufficiency**: Быстрая проверка, accept при score >= 7.0
- **optimality**: Тщательная проверка, accept при score >= 9.0

## Вызов

```python
from skills.triz_critic import critique_generator_output, build_critic_input

critic_input = build_critic_input(
    task_id=task_id,
    task_query=query,
    context=ctx,
    iteration=0,
    mode="sufficiency",
    generator_output=gen_output,
)

report = critique_generator_output(
    critic_input=critic_input,
    llm_call=llm_call,
    logger=logger,
    tokens_callback=tokens_callback,
)
```

## Диагностика

```bash
cd ~/.hermes/profiles/triz-agent
python3 -m skills.triz_critic.test_critic
```