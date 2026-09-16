---
name: ariz-contradiction-resolution
description: ARIZ 8-step structured contradiction resolution (Алгоритм решения изобретательских задач) — step-by-step process with input/operation/output/validation_rule per step. Use for worker↔reviewer conflicts, claim verification, structured analysis of contradictions, and any problem requiring disciplined step-by-step resolution. Targets tribunal-judge, code-auditor, fact-checker. Integrates with triz-problem-solving (principles) and adversarial-critic-checklist (checks).
category: problem-solving
tags: [ARIZ, Contradiction, IFR, IKR, Structured Analysis, Verification, Conflict Resolution]
dependencies: []
---

# ARIZ Contradiction Resolution

## Overview

8-шаговый алгоритм АРИЗ (Алгоритм решения изобретательских задач / Algorithm for Inventive Problem Solving) для агентов opencode. Извлечён из production-архива `triz-agent` (v2.1.1). Каждый шаг имеет: **input** (вход), **operation** (операция), **output** (выход), **validation_rule** (правило валидации).

Skill предназначен для трёх ролей:

- **tribunal-judge** — разрешение конфликтов воркер↔ревьюер, вынесение структурированного вердикта.
- **code-auditor** — структурированный анализ противоречий в коде/архитектуре.
- **fact-checker** — верификация клаймов через дисциплинированный пошаговый процесс.

## When to Use

Активировать, когда:

- Есть конфликт между воркером и ревьюером (два противоположных требования).
- Нужна верификация клайма/утверждения через структурированный процесс.
- Задача требует дисциплинированного пошагового анализа противоречия.
- Нужно сформулировать ИКР (идеальный конечный результат) без указания способа.

## Core Workflow — 8 шагов АРИЗ

Проходи шаги **строго по порядку**. На каждом шаге проверяй `validation_rule` — если правило не выполнено, вернись и доработай выход шага.

### Шаг 1. Анализ задачи (Task Analysis)

- **Input:** `task_query`, `context`
- **Operation:** Выделить цель, систему, надсистему, подсистемы, ограничения, ресурсы
- **Output:** `task_model`
- **Prompt hint:** Сформулируй модель задачи, выделив ключевые элементы и их связи
- **Validation rule:** `task_model` содержит минимум 3 уровня иерархии

### Шаг 2. Формулировка модели задачи (Task Model Formulation)

- **Input:** `task_model`
- **Operation:** Усилить формулировку, выявить конфликтующие пары элементов
- **Output:** `enhanced_model`, `conflicting_pairs`
- **Prompt hint:** Найди пары элементов, которые не могут сосуществовать в текущей форме
- **Validation rule:** `conflicting_pairs` содержит минимум 1 пару

### Шаг 3. Формулировка ИКР (IFR Formulation)

- **Input:** `enhanced_model`
- **Operation:** Сформулировать идеальный результат без указания способа
- **Output:** `ikr`
- **Prompt hint:** Опиши идеальный результат, **НЕ используя** слова «нужно», «следует», «применить»
- **Validation rule:** ИКР не содержит слов «нужно», «следует», «применить»

### Шаг 4. Выявление противоречий (Contradiction Identification)

- **Input:** `enhanced_model`, `ikr`, `conflicting_pairs`
- **Operation:** Сформулировать технические и физические противоречия
- **Output:** `technical_contradictions`, `physical_contradictions`
- **Prompt hint:** Для каждой конфликтующей пары сформулируй: «если улучшить A, то ухудшается B»
- **Validation rule:** минимум 2 противоречия, каждое в канонической форме

### Шаг 5. Оператная зона и время (Operational Zone and Time)

- **Input:** `enhanced_model`, `technical_contradictions`
- **Operation:** Определить пространственные и временные границы вмешательства
- **Output:** `operational_zone`, `operational_time`, `resources`
- **Prompt hint:** Определи: ГДЕ именно и КОГДА именно должно происходить вмешательство
- **Validation rule:** границы конкретны, не размыты

### Шаг 6. Применение приёмов ТРИЗ (Apply TRIZ Principles)

- **Input:** `physical_contradictions`, `operational_zone`, `resources`
- **Operation:** Для каждого противоречия применить 2–3 приёма из матрицы
- **Output:** `raw_solutions`
- **Prompt hint:** Используй приёмы из матрицы противоречий для разрешения каждого физического противоречия
- **Validation rule:** минимум 2 решения на каждое физическое противоречие

### Шаг 7. Синтез концепций (Concept Synthesis)

- **Input:** `raw_solutions`, `ikr`
- **Operation:** Объединить сырые решения в 2–4 целостные концепции
- **Output:** `concepts`
- **Prompt hint:** Сгруппируй решения в 2–4 разнонаправленные концепции
- **Validation rule:** 2–4 концепции, различающихся по ключевому параметру

### Шаг 8. Линеаризация (Linearization)

- **Input:** `concepts`, `ikr`
- **Operation:** Для каждой концепции определить последовательность выполнимых шагов
- **Output:** `linearized_concepts`
- **Prompt hint:** Разбей каждую концепцию на последовательность конкретных шагов с критериями успеха
- **Validation rule:** каждая концепция имеет минимум 3 шага с критериями успеха

## Сводная таблица шагов (Step Summary)

| № | Шаг | Выход | Правило валидации |
|---|-----|-------|-------------------|
| 1 | Анализ задачи | task_model | ≥3 уровня иерархии |
| 2 | Модель задачи | enhanced_model, conflicting_pairs | ≥1 пара |
| 3 | ИКР | ikr | без «нужно/следует/применить» |
| 4 | Противоречия | technical, physical | ≥2 в канонической форме |
| 5 | Оператная зона/время | zone, time, resources | границы конкретны |
| 6 | Приёмы ТРИЗ | raw_solutions | ≥2 решения на противоречие |
| 7 | Синтез концепций | concepts | 2–4 разнонаправленные |
| 8 | Линеаризация | linearized_concepts | ≥3 шага с критериями |

## Integration

- **triz-problem-solving** — knowledge base (18 принципов, матрица противоречий, ИКР templates, ВПР ресурсы). АРИЗ даёт workflow, triz-problem-solving даёт данные.
- **adversarial-critic-checklist** — критическая проверка выходов шагов (особенно ИКР на шаге 3 и концепций на шаге 7).

## Common Pitfalls

- **Пропуск шагов** — АРИЗ работает только при строгом порядке шагов. Не перескакивай.
- **ИКР с нарушителями** — на шаге 3 запрещены «нужно», «следует», «применить» (описывают способ, а не результат).
- **Размытые границы** — на шаге 5 оператная зона и время должны быть конкретными.
- **Одна концепция** — на шаге 7 нужно 2–4 разнонаправленные концепции, не вариации одной.
