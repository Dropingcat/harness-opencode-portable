---
name: coder-dom
description: "Coder DOM capsule — DOM YAML-дерево функций кода (структура, графы CALLS/IMPORTS/STUB/OWNERSHIP, статусы stub/interface/drafted/done). Use when developing a code function, checking function registry, building coder_dom.yaml, routing function ownership, or triaging code stubs/debt."
---

# Coder DOM — работа с капсулой функций

Цель: единый машиночитаемый DOM YAML для кода (аналог Writer DOM), где каждая функция —
узел с сигнатурой, io, контуром, статусом и связями. Это позволяет точечно развивать
функции (мульти-разработка), не теряя прогресс и не дублируя функционал.

## Когда активировать

- Разработка/изменение любой функции в `scripts/`, `packages/`.
- Поиск «кто вызывает/кто использует функцию» (граф CALLS).
- Классификация функции: stub / interface / done.
- Назначение владельца функции (G-ownership) для разделения труда.
- Новый долг по коду → зафиксировать как `CD-*` (префикс Coder) в `config/tech_debt.json`.

## Инструменты (все в `scripts/glossary/`, stdlib-only)

| Скрипт | Назначение |
|---|---|
| `gen_api_index.py` | AST-реестр public функций/классов (signature/doc/contour/index) |
| `call_graph.py` | Рёбра CALLS (функция→вызовы), поле confidence |
| `stub_detect.py` | Классификация: interface (Protocol/ABC) vs stub (pass/NotImpl+маркер) |
| `coder_dom_build.py` | Сборка `coder_dom.yaml` из трёх выше + G-import |
| `coder_dom_schema.json` | JSON Schema контракта `coder-dom/1.0` |

## Рабочий цикл разработки функции

1. Найди функцию-узел в `coder_dom.yaml` (или по `gen_api_index` index).
2. Проверь статус: `stub`/`interface`/`done` (см. `stub_detect`).
3. Измени код (не пересекаясь по строкам с чужими функциями — см. G-ownership).
4. Перегенерируй DOM:
   ```powershell
   python scripts/glossary/coder_dom_build.py --root <root> --out <root>/docs/glossary/coder_dom.yaml
   ```
5. Проверь по схеме: `python -c "import jsonschema,json; jsonschema.validate(json.load(open('coder_dom.yaml')), json.load(open('scripts/glossary/coder_dom_schema.json')))"`.
6. Коммить код + DOM вместе (verify-гейт: перегенерация без diff).

## Правила

- **Не пиши вторую реализацию** — найди существующую функцию по index, развивай её.
- **Пустая функция** → `status: stub` + `# stub: <id>` маркер (или issue-ссылка), иначе недолг.
- **Интерфейсы** (Protocol/ABC) — норма, не долг (stub_detect различает).
- **Долги кодера** — префикс `CD-*` в `config/tech_debt.json` (не TD-*, не файлы).
- **verify-гейт**: после правки генераторов `coder_dom_build` должен давать стабильный fingerprint (JCS-сортировка, `generated_at` вне хэша).

## Источники

- План/архитектура: `scripts/glossary/ARCHITECTURE_PLAN_CODER_DOM.md`.
- Трекер: `scripts/glossary/CODER_DOM_TRACKER.md`.
- Долги: `scripts/glossary/TECH_DEBT_CODER_DOM.md`.