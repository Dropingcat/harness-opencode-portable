# DEV-09 — Live reports are self-modeled (no real tool calls)

Дата: 2026-09-17
Статус: `CONFIRMED / REAL TOOL-CALL TRACE REQUIRED`

## Симптом

4 live-отчёта стабильно возвращают `ESCALATED / no_route_match` для обоих `harness_run`,
даже после фикса (task .min(1) + peer BAD_REQUEST), который подтверждён в dist
(`dist/tools/harness_run.js` содержит `.min(1)`, mtime 21:03).

## Проверка (детерминированная)

1. `dist/tools/harness_run.js` — содержит `.min(1)` ✅ (фикс в dist).
2. `bridge_peer.py` — BAD_REQUEST на пустой task ✅ (peer-тест: `""`→BAD_REQUEST, валидный→route).
3. **Лог OpenCode (`~/.local/share/opencode/log/opencode.log`): НЕТ ни одного фактического
   вызова `harness_run`/`harness_status`** — нет маркеров tool execute, нет no_route_match
   от bridge, нет BAD_REQUEST. Только записи о правках файлов и bash-командах оркестратора.
4. Плагин загружается (run=3b307112, 18:49): `harness plugin loaded ... root=...` — но
   маркер host_version=1.18.16 (fallback), а отчёты говорят 1.18.30 → отчёты писались в
   ДРУГОЙ сессии/процессе.

## Вывод

**Live-отчёты не содержат реальных bridge-ответов.** Модель в OpenCode-сессии описывает
ожидаемое поведение `harness_run` (self-modeled), не вызывая инструмент (или вызовы не
залогированы). Это объясняет:
- почему ESCALATED стабильно, хотя роутер детерминированно работает;
- почему после фикса BAD_REQUEST не появляется (инструмент не вызывается реально);
- почему отчёты писались из другой сессии (host_version 1.18.30 vs 1.18.16 в логе).

## Что НЕ является дефектом

- Роутер Core: работает (проверено 3 путями + peer-тест).
- Контракт tool: фикс корректен (task .min(1)).
- Bridge peer: BAD_REQUEST работает.

## Требуется (неопровержимый live-трасс)

Реальный tool-вызов виден в логе. Способ — CLI с логами:

```powershell
& <opencode-cli> run --dir "E:\Documents\Документы\doc_Opencode_agern-new" `
  --model <пользовательская-модель> --print-logs --log-level INFO --format json `
  "Вызови harness_run с task=\"проверить литературу по теме статьи\" и верни route_id из ответа инструмента."
```

Ожидание после фикса:
- в stdout появится `route_id: academic-research` ИЛИ `CORE_ERROR: BAD_REQUEST` (если без task);
- в логе — маркер вызова инструмента.

## Методология (урок)

Live-калибровка требует **подтверждённого tool-вызова** (из лога/стенда bridge), а не
пересказа модели. Протокол DEV-09 уже это требует; реализация прогона — нет. Зафиксировать:
- каждый harness_run-шаг сопровождать фактическим ответом bridge (копия JSON), полученным
  из сессии, где вызов инструмента РЕАЛЬНО произошёл;
- при сомнении — CLI с --print-logs, где вызовы видны однозначно.

## Действия

1. Прогнать через CLI с --print-logs (детерминированный live-трасс).
2. По результату — обновить DEV09_CALIBRATION_RESULT и закрыть/оставить DEV-09.
3. Отчёты без подтверждённых вызовов помечать `self_modeled: true` и не использовать
   для калибровки порогов.