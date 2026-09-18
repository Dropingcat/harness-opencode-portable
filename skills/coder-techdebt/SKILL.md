---
name: coder-techdebt
description: "Пассивный скилл кодера: сбор и актуализация тех долгов в едином документе проекта (TECH_DEBT_MASTER.md), трассировка создателей записей, пророутинг новых долгов через harness_run (coder-route). Use when creating/updating a tech-debt record, when a new debt/problem is found during coding, or when asked to sync/curate the project debt registry."
---

# Coder TechDebt — сбор и актуализация долгов

Цель: все тех долги проекта собираются в **едином документе** `docs/TRACKERS/TECH_DEBT_MASTER.md`,
каждая запись трассируема (кто/когда/из какой сессии создал), новые долги пророутируются
через `harness_run` (coder-route) для классификации/приоритизации.

## Когда активировать

- Найдена новая проблема/недоделка во время кодинга.
- Нужно обновить/закрыть/дедуплицировать существующий долг.
- Просьба «собрать/синхронизировать/актуализировать тех долги».

## Единый документ

- `docs/TRACKERS/TECH_DEBT_MASTER.md` — сводный, машино-генерируемый из `config/tech_debt.json`
  (см. `scripts/glossary/coder_techdebt_master.py`).
- Префиксы по контурам (не файлы!): `CD-*` Coder, `WR-*` Writer, `RS-*` Researcher,
  `PL-*` plugin, `TD-*` общий/исторический.

## Трассировка создателей

Каждая запись в `config/tech_debt.json` должна иметь:
- `source` — откуда (сессия/агент/файл/ревью);
- `created_by` — автор (например `code-orchestrator`, `general-subagent`);
- `created_at` — дата.

Если запись их не имеет — при актуализации добавить из контекста (не выдумывать:
`unknown` если источник не установлен).

## Пророутинг новых долгов

Новый долг фиксируется так:

1. Записать в `config/tech_debt.json` (префикс по контуру, следующий свободный номер).
2. Пророутить: `harness_run` с route `code-implementation` (или соответствие контуру)
   → получить `coder_dom_hint` → классифицировать (severity/owner/sunset).
3. Перегенерировать мастер: `python scripts/glossary/coder_techdebt_master.py --root <root>`.

## Команды

```powershell
# мастер-документ
python scripts/glossary/coder_techdebt_master.py --root <root>

# сверка: все ли записи в мастере
python scripts/glossary/coder_techdebt_master.py --root <root> --check
```

## Правила

- Не разбрасывать долги по папкам — префиксы в одном `config/tech_debt.json`.
- Не выдумывать автора: `unknown`, если источник не установлен.
- Не переоткрывать закрытое без evidence (reopening event).
- Долг кодера = `CD-*`; параллельная сессия не трогает чужие префиксы.

## Источники

- Реестр: `config/tech_debt.json`.
- Мастер: `docs/TRACKERS/TECH_DEBT_MASTER.md` (генерируется).
- Генератор: `scripts/glossary/coder_techdebt_master.py`.