---
name: adversarial-critic-checklist
description: Adversarial review checklist — structured criticism with 6 checks (domain coverage, fact-concept consistency, concept diversity, source specificity, TRIZ correctness, estimates realism), severity labels (critical/major/minor), and post-validation (forbidden solution verbs in IFR). Use for adversarial review, structured critique, NOT "I don't like it". Targets code-reviewer, tribunal-judge. Integrates with doubt-driven-development (R2 cycle), triz-problem-solving, ariz-contradiction-resolution.
category: review
tags: [Adversarial Review, Critique, Checklist, Severity, Code Review, Verification]
dependencies: []
---

# Adversarial Critic Checklist

## Overview

Структурированная критическая проверка решений для агентов opencode. Извлечена из production-архива `triz-agent` (v2.1.1, роль Критика). Заменяет неструктурированное «мне не нравится» на дисциплинированный чек-лист из 6 пунктов с severity-метками и пост-валидацией.

Skill предназначен для двух ролей:

- **code-reviewer** — adversarial review кода/решений по чек-листу.
- **tribunal-judge** — вынесение вердикта APPROVE/REJECT/REWORK на основе структурированной критики.

## When to Use

Активировать, когда:

- Нужен adversarial review (критика с целью найти слабые места, а не подтвердить).
- Нужна структурированная критика вместо «мне не нравится».
- Нужно проверить решение по чек-листу с severity-метками.
- Нужна пост-валидация ИКР/решений на запрещённые глаголы.

## Чек-лист (6 пунктов)

| ID | Пункт | Описание | Проверка |
|----|-------|----------|----------|
| domain_coverage | Полнота покрытия | Все ли аспекты предметной области учтены? (методы, источники, ограничения, ресурсы) | Наличие разделов: методы, источники, ограничения, ресурсы |
| fact_concept_consistency | Согласованность фактов | Ссылаются ли концепции на конкретные факты из анализа? | Каждая концепция ссылается минимум на 1 источник или факт |
| concept_diversity | Разнонаправленность | Действительно ли концепции разные? (не вариации одной) | Концепции разрешают разные противоречия или используют разные приёмы ТРИЗ |
| source_specificity | Конкретность источников | Есть ли конкретные источники (DOI, URL, названия)? | Минимум 1 источник с DOI или URL |
| triz_correctness | Корректность ТРИЗ | Соответствуют ли применённые приёмы матрице противоречий? | Номера приёмов валидны (1–40) и соответствуют противоречиям |
| estimates_realism | Реалистичность оценок | Реалистичны ли оценки стоимости/времени? | Оценки в разумных пределах для заданного контекста |

## Severity Labels

| Severity | Значение | Действие |
|----------|----------|----------|
| **critical** | Блокирующее замечание | Блокирует принятие (accepted=False) |
| **major** | Требует доработки | Rework; ≥2 major → accepted=False |
| **minor** | Замечание-заметка | Note, не блокирует |

**Правила принятия (accept):**
- `critical` присутствует → **REJECT** (accepted=False).
- `major` ≥ 2 → **REWORK** (accepted=False).
- Иначе → **APPROVE** (accepted=True).

## Post-валидация (Post-validation)

### Запрет глаголов-нарушителей в ИКР

ИКР (идеальный конечный результат) **не должен** содержать слова, описывающие способ достижения:

- «нужно»
- «следует»
- «применить»

Если ИКР содержит эти слова — он описывает способ, а не результат. **REWORK.**

### Проверка глаголов-решений (Solution Verbs)

Проверь, что решение содержит достаточное количество глаголов-действий (≥2), характерных для концепций:

`разделить, объединить, извлечь, заменить, изменить, адаптировать, оптимизировать, декомпозировать, синтезировать, интегрировать, автоматизировать, сократить, расширить, перераспределить, упорядочить, стандартизировать`

Если глаголов-решений < 2 — решение слишком абстрактное, **REWORK.**

## Workflow

1. **Проверь 6 пунктов чек-листа** — для каждого: passed (true/false), score (0.0–1.0), findings, issues.
2. **Назначь severity** каждому issue: critical / major / minor.
3. **Пост-валидация** — проверь ИКР на запрещённые глаголы («нужно», «следует», «применить») и решение на глаголы-действия (≥2).
4. **Вердикт** — APPROVE / REJECT / REWORK по правилам severity.

## Формат отчёта (Report)

```
accepted: true/false
overall_score: 0.0–1.0
severity: 0.0–1.0
check_results: [ {checklist_item_id, passed, score, findings, issues[]} ]
analyst_issues: [ {id, severity, description, evidence, recommendation} ]
designer_issues: [ ... ]
missing_aspects: [ ... ]
recommendations: [ ... ]
```

## Integration

- **doubt-driven-development (R2)** — этот skill даёт чек-лист для цикла сомнений/критики.
- **triz-problem-solving** — проверка корректности приёмов ТРИЗ (пункт triz_correctness).
- **ariz-contradiction-resolution** — структура для анализа противоречий (особенно ИКР на шаге 3).

## Common Pitfalls

- **«Мне не нравится»** — неструктурированная критика запрещена. Всегда проходи 6 пунктов чек-листа.
- **Пропуск severity** — каждое замечание обязано иметь severity (critical/major/minor).
- **ИКР с нарушителями** — «нужно», «следует», «применить» в ИКР → REWORK.
- **Абстрактное решение** — <2 глаголов-действий → REWORK.
- **critical + accepted** — недопустимо (нарушение валидации отчёта).
