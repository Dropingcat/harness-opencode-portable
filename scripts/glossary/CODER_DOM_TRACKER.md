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
- [ ] A4. **Рёбра CALLS** (граф вызовов) — расширить gen_api_index (PyCG/pyan3 или ast-рёбра сами).
- [ ] A5. **Stub-детекция** — пустое тело vs Protocol/ABC; статус `stub`/`interface`.
- [ ] A6. **coder_dom_build.py** — сборка `coder_dom.yaml` из gen_api_index + рёбра + stubs + owners.

## Блок B. Coder DOM YAML (капсула)

- [ ] B1. Схема `coder_dom.yaml` (product+structure+graphs+uncertainty, зеркалит Writer DOM).
- [ ] B2. Графы: G-call (CALLS), G-import (IMPORTS), G-stub (STUB/INTERFACE), G-ownership (OWNED_BY).
- [ ] B3. Поля функции: id, name, signature, io, contour, routing, status, calls, called_by.
- [ ] B4. verify-гейт (pre-commit): перегенерация coder_dom → diff=0 (schema drift fail).

## Блок C. Интеграция и мульти-разработка

- [ ] C1. G-ownership контракт: routing «кто/какой агент развивает функцию».
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