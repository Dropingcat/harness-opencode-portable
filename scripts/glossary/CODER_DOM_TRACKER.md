# Coder DOM Capsule — Local Task Tracker

Дата: 2026-09-18
Скрипт-папка: `scripts/glossary/` (генераторы реестра функций)
Цель: изолированная капсула Coder, где разработка фиксируется как DOM YAML-дерево
(функции + свойства + графы связей), для точечной мульти-разработки и потери ноль.
Связанные TD: TD-074, TD-076, TD-077, TD-078 (+ вложенная спека «на вырост»).

## Легенда статусов
- `[ ]` — TODO; `[~]` — in progress; `[x]` — done.

## Блок A. Фундамент (реестр функций)

- [x] A1. `gen_api_index.py` — AST-реестр public функций/классов (signature/doc/decorators/line/contour/index). (есть)
- [x] A2. `compare_trees.py` — дельта workspace vs portable (PORTABLE_DELTA.md). (есть)
- [x] A3. `render_glossary.py` — рендер GLOSSARY.md из JSON. (есть)
- [x] A4. **Рёбра CALLS** — `call_graph.py` (stdlib ast, поле confidence; 1804 узла/1522 рёбра workspace, 641/1289 portable).
- [x] A5. **Stub-детекция** — `stub_detect.py` (interface=Protocol/ABC vs stub=pass/NotImpl+маркер; 23 интерфейса, 0 стубов).
- [x] A6. **coder_dom_build.py** — сборка `coder_dom.yaml` (752 функции, 18 контуров workspace; 641/11 portable; детерминирован).

## Блок B. Coder DOM YAML (капсула)

- [x] B1. Схема `coder_dom.yaml` (product+structure+graphs+uncertainty, зеркалит Writer DOM) + `coder_dom_schema.json` (JSON Schema coder-dom/1.0, валиден).
- [~] B2. Графы: G-call (CALLS), G-import (IMPORTS), G-stub (STUB/INTERFACE), G-ownership (OWNED_BY). [G-call/G-import/G-stub в build; G-ownership — ручной слой, TODO]
- [x] B3. Поля функции: id, name, signature, io, contour, routing, status, calls, called_by. (в build)
- [x] B4. verify-гейт: erify_coder_dom.py (перегенерация → diff=0; MISSING/STALE → rc1; --fix для генератора). (done)

## Блок C. Интеграция и мульти-разработка

- [x] C1. G-ownership: в build (assignments, DEFAULT по контуру, внешний файл).
- [ ] C2. Адаптеры: Writer/Researcher/Coder/dialogue (порты из спеки semantic_field).
- [ ] C3. Кэш/провенанс: source_hash+config_hash+module_versions.
- [ ] C4. E2E: взять функцию-узел → изменить → перегенерировать DOM → коммит (код+DOM).

## Блок D. Долги и качество

- [ ] D1. TD-078: разделить 23 stub/interface-функции (Protocol vs заглушки), зафиксировать в реестре.
- [ ] D2. TD-077: контракты reviewer/tester с evidence исполнения.
- [ ] D3. Инвентаризация stubs в `coder_dom.yaml` G-stub.

## Остаток (после B-C)
- [ ] E1. semantic_field модульная сеть (спека из 87 секций) — «на вырост».
- [ ] E2. Виртуальные E2E (парафраз/перестановка/модальность/причинность/квалификатор).