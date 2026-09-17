# DEV-09 — Re-run: stale plugin cache suspected

Дата: 2026-09-17
Статус: `FIX_IN_DIST / LIVE_RE_RUN_REQUIRED_AFTER_RESTART`

## Состояние после фикса

- `src/tools/harness_run.ts`: `task ... .min(1)` — применено.
- `dist/tools/harness_run.js` (mtime 21:03): содержит `.min(1)` — **dist актуален**.
- `bridge_peer.py`: BAD_REQUEST на пустой task — применено, peer-тест подтвердил
  (`task=""` → CORE_ERROR/BAD_REQUEST, `task="проверить литературу"` → academic-research).
- TS-тесты 12/12, Coder 139.

## Live-прогон (после фикса) всё ещё ESCALATED

Второй live-отчёт вернул `route_id: "EMPTY"` / `state: ESCALATED` для обоих harness_run.
Это НЕ соответствует ни фиксу (должен быть BAD_REQUEST при пустом task), ни валидному
вызову (должен быть route_id).

**Наиболее вероятная причина: OpenCode Desktop держит плагин из СТАРОГО dist в памяти.**
Плагин загружается при старте процесса/сессии и кэшируется; `.min(1)` в dist не подхватится,
пока приложение не перезапущено полностью.

## Действие (для пользователя)

1. **Полностью закрыть OpenCode Desktop** (не только сессию — процесс).
2. Открыть проект заново (плагин перечитает dist).
3. Проверить в логе маркер загрузки: `harness plugin loaded ... root=...`.
4. Повторить запрос-ловушку.

## Ожидание после корректной перезагрузки

- Если модель передаст `task` (теперь обязателен схемой) → `route_id` корректный
  (`academic-research` / `code-implementation`).
- Если модель попытается вызвать без `task` → schema-валидация отклонит вызов ИЛИ
  peer вернёт `CORE_ERROR: BAD_REQUEST` (не ESCALATED/no_route_match).
- Любой из этих двух исходов подтвердит, что фикс дошёл до live.

## Если после полного рестарта всё ещё ESCALATED

Тогда проблема глубже (например, OpenCode запускает плагин из другого корня,
`.opencode/opencode.json` указывает на другой dist, или `OPENCODE_HARNESS_ROOT`
резолвится иначе). Тогда нужно собрать диагностику:
- полный лог сессии (`--print-logs --log-level DEBUG`);
- фактический путь загруженного dist (из лога плагина);
- `route_id` из bridge-ответа (не пересказ).