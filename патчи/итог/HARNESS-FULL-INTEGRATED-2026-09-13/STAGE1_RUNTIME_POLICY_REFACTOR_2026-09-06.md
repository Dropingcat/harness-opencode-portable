# Stage 1 — Runtime policy compiler refactor

Дата: 2026-09-06

## Выполнено

1. Создан `routes_authority.json` как единый редактируемый источник route semantics.
2. Tool usage contracts вынесены в `tool_contracts_authority.json`.
3. Создан manifest authoritative/generated inputs.
4. Реализован fail-closed compiler `scripts/router/compile_runtime.py`.
5. Создаётся детерминированный `runtime_snapshot.json` с `policy_hash` и hashes всех sources.
6. `profile_routes.json`, `tool_skill_routes.json`, `skill_to_route_map.json`, `skills_graph.json` переведены в generated compatibility views.
7. Python resolver переведён на snapshot-only runtime.
8. TypeScript plugin больше не содержит hardcoded route/tool policy и загружает snapshot.
9. `add_skill.py` изменяет route authority вместо generated route map.
10. Capsule registry обновлён, чтобы generated файлы больше не назывались source-of-truth.
11. Добавлены regression tests на freshness/hash/snapshot-backed resolver.

## Ошибки, обнаруженные compiler-валидацией

При первой сборке compiler заблокировал snapshot из-за уже существовавших несогласованностей:

- `markitdown` использовался route, но отсутствовал в skill registry;
- `autoresearch` использовался route, но отсутствовал в skill registry;
- `triz-problem-solving` использовался route, но отсутствовал в skill registry;
- `triz-architecture` использовал `code` capsule, хотя capsule не объявляла поддержку этого route.

Ошибки исправлены в authoritative configs. Валидатор не ослаблялся.

## Проверки

- `python scripts/router/compile_runtime.py --check` — PASS.
- `python -m unittest discover -s tests -v` — 9/9 PASS.
- `python -m compileall -q scripts mcp guard tests` — PASS.
- smoke route: `проведи аудит кода и исправь слабые места` → `code-review`, `standard`, `worker_reviewer_tester`, snapshot-backed, policy hash присутствует.

## Оставшиеся ограничения

- TypeScript plugin не имеет отдельного локального package/tsconfig в модуле, поэтому полноценный type-check зависит от OpenCode plugin dependency в целевом окружении. Политика из него удалена, но integration test лучше добавить в окружении, где установлен `@opencode-ai/plugin`.
- `routes_authority.json` пока является hand-authored JSON. Следующий возможный шаг внутри stage 1.5: JSON Schema/Pydantic model и typed config migration.
- Compiler валидирует ссылки и compatibility, но пока не проверяет семантическое перекрытие regex routes и unreachable routes. Это желательно добавить отдельным lint, а не смешивать с core compile semantics.
