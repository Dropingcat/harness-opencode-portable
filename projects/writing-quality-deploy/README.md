# writing-quality-0.2.3-v2 — развёртывание в harness (2026-10-25)

## Что это

Архив `F:\1\_STRUCTURED\_AGENT_TECH\writing-quality-0.2.3-v2.zip` — **не MCP**. Это
плагин-бандл скиллов (формат Claude Code / Codex): 4 скилла + Python-валидаторы.
Никаких MCP-серверов и JS-плагина в составе нет.

## Диагноз дрейфа защищённых хешей

`scripts/verify_bundle.py` в архиве падал (`valid: false`):
`protected_subtrees` в `bundle-spec.json` расходились с фактическим контентом
двух скиллов. Разбор:

- файлы в zip **побайтово идентичны** апстрим-ветке `main`
  (github.com/Israelmusondaayliffe/plugins, все 10 файлов двух поддеревьев — SAME);
- зафиксированные в `bundle-spec.json` хеши (`aa79e3da…`, `8eca04e0…`) не
  соответствуют контенту **даже в самом апстриме** — скиллы правили после
  фиксации spec, а spec не пересобрали. Дефект апстрима, контент каноничен.
- Исправление: pinned-хеши пересчитаны под фактический контент
  (`c8b4fcd2…`, `52b1c0c6…`) — только в развёрнутой копии, файлы скиллов не тронуты.

## Размещение

| Путь | Назначение |
|---|---|
| `E:\opencode_harness_portable\packages\writing-quality\` | Целостный бандл (источник, verify_bundle проходит) |
| `E:\opencode_harness_portable\.opencode\skills\{4 скилла}\` | **Регистрируемая** копия — рантайм opencode подхватывает скиллы отсюда |
| `E:\opencode_harness_portable\skills\opencode-current\{4 скилла}\` | Зеркало/reference (по конвенции `skills/README.md`) |

В `.opencode/opencode.json` никаких правок не делалось — скиллы из
`.opencode/skills/` обнаруживаются автоматически.

## Проверки (все зелёные)

- `scripts/verify_bundle.py` → `valid: true`, 47 паттернов, 19 файлов engine, 0 errors;
- `python -m unittest discover -s tests` → **11/11 OK**;
- `engine_check.py` → `status: complete`;
- валидаторы скиллов под `.venv` harness: `validate_claim_ledger.py`,
  `validate_route.py`, `quality_validator.py`, `voice_profiler.py` → exit 0;
  `check_business_doc.py` → warning на слабом интенте (штатное поведение детектора);
- рантайм (standalone CLI из harness): все 4 id зарегистрированы —
  `business-writing-intent-enforcer`, `claim-boundary-checker`,
  `writing-enforcer`, `writing-quality-router` (пути → `.opencode/skills/...`).

## Замечание

Скилл `paper-review` (прошлый порт) лежит в `skills/opencode-current/paper-review`
и в рантайме зарегистрированным скиллом **не является** — проектные скиллы
opencode читает из `.opencode/skills/`. Это прецедентный пробел прошлого порта,
вне рамок текущей задачи.