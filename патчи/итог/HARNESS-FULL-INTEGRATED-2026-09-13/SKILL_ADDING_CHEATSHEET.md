# Как добавить skill в систему (шпаргалка)

Официальный способ — один детерминированный скрипт.
Он обновляет ВСЕ связанные места и сразу проверяет граф/роутер.

## Один вызов делает всё

```bash
python scripts/add_skill.py \
  --name <skill-name> \
  --class <core|optional|reference> \
  --capsule <capsule-id> \
  --route <route-id> \
  [--live]
```

### Обновляемые файлы (автоматически)

| # | Файл | Что делает |
|---|------|-----------|
| 1 | валидация | проверяет `SKILL.md` + frontmatter `name/description` |
| 2 | `config/skills_registry.json` | добавляет в `core_runtime_skills` / `optional_domain_skills` / `reference_only_skills` |
| 3 | `config/skill_capsule_policy.json` | добавляет в `provided_skills` выбранной capsule |
| 4 | `config/skill_to_route_map.json` | добавляет в `skills` выбранного route |
| 5 | `config/skills_graph.json` | пересобирает граф (nodes/edges) |
| 6 | router check | прогоняет `resolve_route.py` на route |
| 7 | live | (опция `--live`) копирует в `~/.config/opencode/skills/<name>` |

## Примеры

```bash
# core-скил, привязать к research capsule + academic route, синхронизировать в live
python scripts/add_skill.py --name literature-review --class core \
  --capsule research-core --route academic-research --live

# optional-скил, только registry + граф, без live
python scripts/add_skill.py --name my-domain-skill --class optional

# добавить без пересборки графа (если граф правили руками)
python scripts/add_skill.py --name x --class optional --no-graph
```

## Валидные значения

- `--class`: `core` | `optional` | `reference`
- `--capsule`: существующие id в `skill_capsule_policy.json` (например `core-orchestration`, `code`, `research-core`, `integration-config`, `writing`)
- `--route`: существующие id в `skill_to_route_map.json` (например `code-implementation`, `academic-research`, `web-research`, `writing-prose`)

## Where skill физически должен лежать

Скрипт ищет `SKILL.md` в:
- `skills/server2-corpus/<name>/SKILL.md`
- `skills/opencode-current/<name>/SKILL.md`

Если скила нет на диске — сначала положи его в одну из этих папок (например через git clone официального skill), затем вызови скрипт.

## Правила

1. **Проверяй, что у скила есть `SKILL.md` с frontmatter** (`name` + `description`) — скрипт не даст добавить без этого.
2. **`--live`** синхронизирует только после успешной регистрации (не патчит live при ошибке).
3. После добавления **перезапусти OpenCode**, чтобы скил подхватился.
4. Если нужно связать skill с tool/MCP — дополнительно правь `config/tool_runtime_bindings.json` (не через скрипт).