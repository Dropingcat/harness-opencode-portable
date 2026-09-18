---
name: glossary-registry
description: Автоматически пересобирает реестр функций harness (function_index.json + GLOSSARY.md + PORTABLE_DELTA.md + IMPLEMENTATION_STATUS) и синхронизирует docs/glossary между полным деревом и portable. Используй для «обнови реестр/глоссарий», «пересобери функции».
---

# Glossary Registry

Автоматическая пересборка и синхронизация реестра функций harness между полным рабочим деревом и portable-деревом.

## Когда использовать

Триггеры — задача относится к реестру функций / глоссарию / инвентаризации API harness:

- «обнови реестр функций», «пересобери глоссарий», «обнови docs/glossary»;
- «покажи, что реализовано в harness / чего не хватает в portable»;
- «синхронизируй функцию X в portable» — сначала пересборка реестра, потом анализ дельты;
- любой диф между workspace и portable по составу модулей/функций/классов;
- обновление счётчиков в `IMPLEMENTATION_STATUS.md`.

НЕ использовать для: ревью кода, написания кода, правки `scripts/glossary/*.py` (генераторы — чужая зона, только запуск).

## Команды пересборки

Все команды запускать с `$env:PYTHONIOENCODING="utf-8"` (консоль Windows, иначе кракозябры в JSON/MD).

### 1. Полное дерево (workspace)

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/glossary/gen_api_index.py --root "E:\Documents\Документы\doc_Opencode_agern-new" --out "E:\Documents\Документы\doc_Opencode_agern-new\docs\glossary\function_index.json" --label workspace
```

### 2. Portable-дерево

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/glossary/gen_api_index.py --root "E:\opencode_harness_portable" --out "E:\opencode_harness_portable\docs\glossary\function_index.json" --label portable
```

### 3. Рендер GLOSSARY.md (оба дерева)

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/glossary/render_glossary.py --index "E:\Documents\Документы\doc_Opencode_agern-new\docs\glossary\function_index.json" --out "E:\Documents\Документы\doc_Opencode_agern-new\docs\glossary\GLOSSARY.md" --label workspace
python scripts/glossary/render_glossary.py --index "E:\opencode_harness_portable\docs\glossary\function_index.json" --out "E:\opencode_harness_portable\docs\glossary\GLOSSARY.md" --label portable
```

### 4. Дельта workspace → portable

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/glossary/compare_trees.py --base "E:\Documents\Документы\doc_Opencode_agern-new\docs\glossary\function_index.json" --target "E:\opencode_harness_portable\docs\glossary\function_index.json" --out "E:\Documents\Документы\doc_Opencode_agern-new\docs\glossary\PORTABLE_DELTA.md"
Copy-Item -Force "E:\Documents\Документы\doc_Opencode_agern-new\docs\glossary\PORTABLE_DELTA.md" "E:\opencode_harness_portable\docs\glossary\PORTABLE_DELTA.md"
```

### 5. Синхронизация генераторов в portable

```powershell
Copy-Item -Force "E:\Documents\Документы\doc_Opencode_agern-new\scripts\glossary\*.py" "E:\opencode_harness_portable\scripts\glossary\"
```

(генераторы `gen_api_index.py`, `render_glossary.py`, `compare_trees.py` должны быть идентичны в обоих деревьях)

### 6. Обновление IMPLEMENTATION_STATUS.md

Раздел счётчиков (после пересборки прочитать `meta.counts` из обоих JSON):

```text
Реестр функций (2026-09-18):
- workspace: modules=N, functions=N, classes=N, methods=N
- portable:  modules=N, functions=N, classes=N, methods=N
- дельта:    modules_missing=N, functions_missing=N
```

Счётчики брать из `meta.counts` обоих `function_index.json`; дельту — из сводной таблицы `PORTABLE_DELTA.md` (сумма колонок «Модулей нет в target» / «Функций нет в target» по контурам). Обновить дату и число. Остальное содержимое файла НЕ переписывать.

## Проверка (smoke)

После пересборки обязательно прогнать:

```powershell
$env:PYTHONIOENCODING="utf-8"
python -c "import json; w=json.load(open(r'E:\Documents\Документы\doc_Opencode_agern-new\docs\glossary\function_index.json', encoding='utf-8')); p=json.load(open(r'E:\opencode_harness_portable\docs\glossary\function_index.json', encoding='utf-8')); assert w['meta']['counts']['modules']>0 and p['meta']['counts']['modules']>0; print('json OK:', w['meta']['counts'], p['meta']['counts'])"
```

Критерии прохождения:
1. оба JSON валидны (`json.load` без ошибок) и `meta.counts.modules > 0` (а также functions/classes);
2. `GLOSSARY.md` содержит ключевые функции `resolve` и `verify_claim`;
3. `PORTABLE_DELTA.md` содержит ненулевые значения «модулей нет в target» (`modules_missing > 0`) — то есть дельта не пустая.

Если smoke не прошёл — НЕ коммитить, разобраться и перегенерировать.

## Git

Коммит в ОБА репозитория (workspace и portable) с одинаковым сообщением:

```powershell
git add docs/glossary scripts/glossary
git commit -m "chore(glossary): refresh registry"
```

Порядок: сначала workspace, затем portable. Ничего лишнего в коммит не включать (только `docs/glossary/*` и синхронизированные `scripts/glossary/*.py`).

## Важно

1. **НЕ редактировать** generated-артефакты роутера и чужие модули — только пересобирать реестр по командам выше.
2. **НЕ трогать чужой код** — `scripts/glossary/*.py` только запускать и копировать, не менять.
3. **Всегда** ставить `$env:PYTHONIOENCODING="utf-8"` перед запуском Python-скриптов.
4. Порядок строгий: 1→2→3→4→5→6→smoke→git. Пропуск шага ломает согласованность артефактов.
5. `IMPLEMENTATION_STATUS.md` — частично ручной файл: обновлять только раздел счётчиков реестра, остальное не трогать.