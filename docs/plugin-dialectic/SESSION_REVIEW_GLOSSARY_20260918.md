# Code Review — сессия «Сбор недостающих функций в глоссарий» (2026-09-18)

Статус: `REVIEW COMPLETE / M1 DONE / M2-M6 PREEMPTED`
Сессия: `ses_f4c9bd5bcffeL1GIYCA5drW3Pu` (параллельная, прервана пользователем на M2)
Цель сессии: глубокая ревизия и сбор всех функций, отсутствующих в `docs/glossary`,
для кросс-использования «по принципу Python-библиотек» (JSON + генератор, в оба дерева).

## 1. Что сессия сделала хорошо

| Шаг | Результат | Оценка |
|---|---|---|
| Ритуал старта (капсула, project_context, принципы) | выполнен | ✅ |
| Исследование структуры (2 дерева, контуры, мусор/бэкапы) | доскональное: 7774 vs 5687 py, идентичность workspace=opencode_harness, дельта контуров | ✅ |
| Guard preflight (P0 BLOCK на исторической базе → анализ текущей сессии) | корректно отделила историю от текущей задачи | ✅ |
| Вопросы пользователю (4: база/куда/формат/глубина) | заданы, ответы получены | ✅ |
| M1: `scripts/glossary/gen_api_index.py` (AST-генератор) | написан (373 строки, stdlib, контуры+index, исключения мусора) | ✅ |
| Фабрика: init GLOSSARY-REVISION-20260918 | RUNNING | ✅ |

## 2. Затруднения и ошибки (объективно, с evidence)

| # | Проблема | Evidence | Severity |
|---|---|---|---|
| E1 | **cp1251-баг `project_context.py`**: `UnicodeEncodeError: 'charmap' codec can't encode '\u2192'` при выводе JSON (кириллический путь + cp1251). Сессия обходила через `PYTHONIOENCODING=utf-8`. | traceback в сессии; повторён (с PYTHONUTF8=1 работает, без — падает) | major |
| E2 | **PowerShell искажает кавычки** в `python -c` (многократные SyntaxError: unterminated string literal) — сессия тратила много шагов на обход (писала temp-скрипты). | 5+ SyntaxError в дампе | minor (инфраструктура) |
| E3 | **Guard P0 BLOCK на полной базе** (49164 партов, 600 untrusted) из-за исторических сессий — потребовало ручного разбора «текущая сессия чистая». | guard_out.json: BLOCK/P0/FAIL | major (guard-шум) |
| E4 | **M2 не выполнен**: `function_index.json` не создан (генератор написан, но не прогнан). Сессия прервана (MessageAbortedError) после init фабрики и перед прогоном. | function_index.json отсутствует | critical (недоделка) |
| E5 | **M3-M6 не начаты**: нет PORTABLE_DELTA.md, нет рендера GLOSSARY, нет smoke-тестов. | файлы отсутствуют | critical |
| E6 | `db_sessions.py` считал tools как `'?'` (500) — структура provider в part не так, как предполагал скрипт; диагностика частично бесполезна. | TOOLS in last 500: {'?': 500} | minor |

## 3. Что из Harness могло использоваться, но НЕ использовано

| Возможность Harness | Почему полезна | Не использовано |
|---|---|---|
| **`sync_to_live.py`** (существует в scripts) | для синхронизации docs/glossary в оба дерева вместо ручного Copy-Item | ✅ не использован |
| **`kanban_report.py`** (ритм отчётов) | для канбан-отчёта по шагам; сессия только init-нула фабрику, без report | ✅ не использован |
| **`character_sheet.py` / память L3** | уроки прошлых сессий (cp1251, PowerShell-кавычки) — есть в memory_registry | ✅ не проверял memory (только project_context) |
| **`guard/src/session_guard.py` напрямую по текущей сессии** | сессия хотела guard-чек именно текущей сессии, но пошла в ручной sqlite-разбор вместо готового скрипта | ✅ не использован |
| **`researcher_core/guard.py` (scan_text)** | готовая функция сканирования untrusted текста — сессия писала свой sqlite-парсер | ✅ не использован |
| **`contract_validator.py` / `state_reducer.py`** | для валидации JSON-выхода воркера (M1) детерминированно | ✅ не использован (submit бы проверил) |
| **`config/memory_registry.json`** | уроки про cp1251/PowerShell (зафиксированы ранее) — сессия их не читала | ✅ не использован |

## 4. Дерево/версии (уточнение для будущей работы)

- **Workspace** `E:\Documents\Документы\doc_Opencode_agern-new` = `E:\opencode_harness` (идентичны, 7774 py) — полный живой код.
- **Portable** `E:\opencode_harness_portable` (5687 py) — GitHub v1 (чистый), готовится v1.1.
- **Дельта контуров (в portable отсутствуют):** `capsules`, `kanban`, `memory`, `remote_acceptance`, `research`, `writer`, `writer_core_handoff` (+ `verify_claims.py`, demos).
- Это ровно то, что по ROADMAP_v1.1 (TD-D1) надо переносить в v1.1.

## 5. Рекомендации (контракт для завершения M2-M6)

1. **M2**: прогнать `gen_api_index.py --root <полное> --label workspace` и `--root <portable> --label portable` → 2 JSON.
2. **M3**: скрипт сравнения (по контурам/функциям) → `PORTABLE_DELTA.md` (карта переноса v1.1).
3. **M4**: рендер `GLOSSARY.md` из JSON (по контурам, сигнатуры+doc).
4. **M5**: записать в docs/glossary **обоих** деревьев (или через sync_to_live.py).
5. **M6**: smoke (JSON валиден, py_compile), ревью воркера, канбан-отчёт, память L3.
6. Починить cp1251 в project_context (PYTHONIOENCODING/`sys.stdout.reconfigure`) — иначе каждый новый агент спотыкается (E1).

## 6. Техдолги (новые, в config/tech_debt.json)

- **TD-073**: project_context.py падает с UnicodeEncodeError на cp1251 (кириллический путь) — нужен reconfigure stdout.
- **TD-074**: registry-генератор M1 написан, но M2-M6 (прогон, дельта, рендер, синк, smoke) не завершены — долг на завершение.
- **TD-075**: sync-процедура docs между workspace/portable не автоматизирована (ручной Copy-Item; `sync_to_live.py` не использован).
- **TD-076**: кодеру нужен DOM-аналог для функций кода (как Writer DOM YAML): манифест с блоком-клаймом на функцию и связями, дополняемый при разработке.

## 8. Кодерский DOM-аналог (TD-076) — уточнение

У Writer есть `DOM YAML` (структура документа, где каждый параграф несёт блок claims + связи/графы). У Coder такого нет. Задача TD-076 — по аналогии:

```yaml
# code_dom.yaml (концепт)
functions:
  - id: "F-001"
    name: "resolve"
    signature: "resolve(task_text: str, hints: dict|None=None) -> dict"
    contour: "router"
    module: "scripts/router/resolve_route.py"
    calls: ["load_snapshot", "match_routes"]          # связи
    called_by: ["harness.run", "resolve_bundle"]      # кто использует
    uses: ["runtime_snapshot.json"]                   # данные
    claims:                                           # клаймы функции
      - "маршрутизирует task -> route_id/bucket"
    status: "active"
```

Блок на функцию = клайм (функция + сигнатура + связи + кто использует). Манифест
машинно-генерируется из AST (`gen_api_index.py`, TD-074) и дополняется при разработке.
Это даёт перекрёстную навигацию (как GLOSSARY, но машино-читаемо), базу для
ревью/тестов/трибунала кода.

## 7. Закрыто/подтверждено

- Дельта контуров подтверждена (7 контуров отсутствуют в portable) — карта для v1.1.
- Генератор M1 качественный (stdlib, детерминированный, исключения мусора).