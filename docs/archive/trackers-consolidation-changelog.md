# Trackers Consolidation — Changelog

Дата: 2026-09-15.
Ветка: main (plugin/dialectic/dev-trackers).

## Что изменено

1. **`config/tech_debt.json`** — заменён с legacy r0 (6 записей) на канонический реестр
   (65 записей, version 2), перенесённый из `патчи/миграция в плагин/tech_debt_current.json`.
   Схема совместима с `project_context.py` (`debts[].status`: open/closed).
   Итог: **65 total / 50 open / 15 closed**.

2. **`config/development_tracker.json`** — новый глобальный трекер разработки:
   DEV-01..13 + WS-55A..59A + критический путь DEV-03→04→05→09.
   Итог: **3 done / 3 in_progress / 7 not_started**.

3. **`docs/archive/tech-debt-archive.md`** — архив legacy r0-реестра и 15 CLOSED_REPORTED
   записей с правилом «закрытие не переоткрывается; регрессия = reopening event».

## Актуальные возможности развития ветки (plugin/dialectic)

- **DEV-05 (in progress)**: Tribunal уже на `PluginBridgeProviderTransport`
  (Q1/A1/Q2/A2/Q3 deterministic, живой load+tools на OpenCode 1.18.30).
  Следующее: Coder/Writer конвергенция на единый `semantic.execute` (TD-062).
- **DEV-09 (not_started)**: требует живого production provider trace — после DEV-05.
- **Научный слой (DEV-11/12/13 = TD-046/047/048/049/050)**: может идти виртуальными E2E,
  не дожидаясь live.

## Следующие шаги по трекеру (критический путь)

1. `DEV-05` Coder-конвергенция (перенос coder semantic invocation на plugin bridge);
2. `DEV-05` Writer-конвергенция;
3. `DEV-09` live calibration.

## Формат

Каждый шаг разработки коммитится отдельно; изменения долга/возможностей фиксируются
в этом файле (или в `docs/plugin-dialectic/`).