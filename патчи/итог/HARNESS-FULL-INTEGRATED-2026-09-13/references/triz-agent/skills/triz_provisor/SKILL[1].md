---
name: triz-provisor
version: 1.0.0
description: >
  Навык Провизора ТРИЗ-агента. Супервизор, который управляет циклом,
  оценивает итерации, принимает решения STOP/CONTINUE и синтезирует
  финальную рекомендацию.
---

# Skill: triz-provisor

## Описание
Навык Провизора ТРИЗ-агента. Супервизор, который:
- Хранит TRIZ_MEMORY и ARIZ_MEMORY
- Считает метрики (2/4 кодом, 2/4 LLM)
- Принимает решения STOP/CONTINUE
- Синтезирует финальную рекомендацию
- Оркестрирует цикл Генератор → Критик → Оценка

## Роль в архитектуре
Провизор — центральная роль:
- **Провизор** — управляет циклом (ЭТОТ НАВЫК)
- **Генератор** — выполняет АРИЗ, генерирует концепции
- **Критик** — проверяет качество

## Ключевые функции

### `evaluate_iteration()`
Оценка итерации:
- `completeness = min(1.0, len(concepts) / target)` — кодом
- `coherence = 1 - (n_issues / n_checks)` — кодом
- `feasibility` — через LLM (с rule-based fallback)
- `novelty` — через LLM (с rule-based fallback)
- `overall = (c + c + f + n) / 4 * 10`

### `decide_continue()`
Решение о продолжении:
- `STOP_QUALITY` если `overall >= threshold`
- `STOP_LIMIT` если `iteration >= max_iterations`
- `STOP_PLATEAU` если плато качества
- `CONTINUE` иначе

### `synthesize_final()`
Синтез финальной рекомендации:
- Выбор лучшей концепции (по idealness)
- Обоснование выбора
- Запасные варианты
- Риски

### `run_triz_cycle()`
Полный цикл ТРИЗ-агента:
1. Создание задачи в канбане
2. Цикл: Генератор → Критик → Оценка → Решение
3. Финальный синтез
4. Завершение задачи

## Rule-based fallback
При отказе LLM (circuit breaker open):
- feasibility/novelty = среднее по истории (или 0.5 по умолчанию)
- STOP-решения по формулам из спецификации
- Синтез выбирает концепцию с максимальной idealness

## Метрики
Каждое действие логируется:
- `provisor_evaluate` — оценка итерации
- `provisor_synthesize` — финальный синтез

## Входные данные
```
ProvisorInput {
  "task_id": "uuid",
  "task_query": "...",
  "context": {...},
  "mode": "sufficiency|optimality",
  "triz_memory": {...},
  "ariz_memory": {...}
}
```

## Выходные данные
```
FinalRecommendation {
  "task_id": "...",
  "total_iterations": N,
  "mode": "...",
  "recommended_concept": {...},
  "justification": [...],
  "fallback_concepts": [...],
  "risks": [...],
  "final_evaluation": {...},
  "stop_reason": "..."
}
```

## Зависимости
- `kanban/` — управление задачами
- `memory/` — TRIZ_MEMORY, ARIZ_MEMORY, режимы
- `metrics/` — логирование
- `resilience/` — circuit breaker, идемпотентность
- `skills/triz-generator/` — вызов Генератора
- `skills/triz-critic/` — вызов Критика

## Тестирование
```bash
cd ~/.hermes/profiles/triz-agent
python -m skills.triz_provisor.test_provisor
```

## Оценка итерации (детально)

| Метрика | Источник | Диапазон |
|---------|----------|----------|
| completeness | Код | 0.0 - 1.0 |
| coherence | Код | 0.0 - 1.0 |
| feasibility | LLM (fallback: код) | 0.0 - 1.0 |
| novelty | LLM (fallback: код) | 0.0 - 1.0 |
| overall | Формула | 0.0 - 10.0 |
| improvement_delta | Формула | -10.0 - 10.0 |