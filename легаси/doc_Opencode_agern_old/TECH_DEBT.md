# Tech Debt — отдельный учет для кодеров

> Техдолг ведется отдельно от фич. Смешение — главный источник "Fixes that Fail".

## 1. Принцип

- Техдолг — это контракт с Sunset Clause, а не TODO в голове. Нет записи в реестре → нет долга.
- Каждый долг имеет владельца (WP/агент), severity, триггер пересмотра и стоимость откладывания.
- Долг всегда привязан к конкретному противоречию или слабому месту из TRIZ/ARIZ (иначе это не долг, а хотелка).

## 2. Реестр: `config/tech_debt.json` (создать при первой записи)

```json
{
  "version": 1,
  "debts": [
    {
      "id": "TD-001",
      "title": "Хардкод /home/orangepi в mcp launchers",
      "area": "mcp/launchers/_runner.py, coder_router_server.py",
      "kind": "portability",
      "severity": "high",
      "introduced_in": "bundle pass 1",
      "contradiction": "portability vs speed — Linux paths ускоряли Pi, ломают Windows",
      "impact": "launchers не работают на Windows без env",
      "owner": "code-orchestrator",
      "created_at": "2026-08-31",
      "sunset_at": "2026-09-14",
      "review_trigger": "при подключении первого launcher в opencode.jsonc",
      "acceptance": "все paths через OPENCODE_BIN/OPENCODE_HARNESS_ROOT/OPENCODE_RUNS_DIR, py_compile + smoke pass",
      "cost_if_delayed": "блокирует сервис-делегаты и profile_config",
      "status": "open"
    }
  ]
}
```

Поля обязательны: `id`, `title`, `area`, `kind`, `severity`, `owner`, `sunset_at`, `acceptance`, `status`. `severity`: `critical|high|medium|low`.

## 3. Инвентарь на 2026-08-31 (из аудита bundle)

| ID | Долг | Area | Severity | Sunset | Владелец |
|---|---|---|---|---|---|
| TD-001 | Хардкод Linux путей | `mcp/launchers/_runner.py`, `mcp/coder_router_server.py`, `agents/*.md` | high | 2026-09-14 | code-orchestrator |
| TD-002 | Plugin hook не зарегистрирован в runtime | `plugins/tool-skill-contract-router.ts`, `opencode.jsonc` | high | 2026-09-07 | profile_config |
| TD-003 | Дублирование route данных (JSON vs TS) | `config/tool_skill_routes.json` vs `plugins/*.ts` | medium | 2026-09-14 | code-orchestrator |
| TD-004 | Guard env не прокинут (OPENCODE_SESSION_DB) | `config/guard_policy.json`, `plugins/*.ts` | high | 2026-09-07 | profile_config |
| TD-005 | Source-fetcher fallback не покрыт тестом | `agents/source-fetcher.md`, `mcp/academic_search_server.py` | medium | 2026-09-21 | code-tester |
| TD-006 | Отсутствует `config/tech_debt.json` файл | `config/` | low | 2026-09-07 | code-orchestrator |
| TD-007 | Нет единого `docs/` индекса (док-контроллер) | `README.md`, `MANIFEST.md`, `references/` | medium | 2026-09-14 | code-orchestrator |
| TD-008 | WP-0 контракты не сгенерированы как JSON Schema | `references/agent-kirpichik/CONTRACTS.md` | medium | 2026-09-21 | code-orchestrator |
| TD-009 | Runtime core не был импортирован в сам модуль | `shared/`, `scripts/code-factory/`, `W:\server2\scripts\code-factory` | critical | 2026-09-07 | code-orchestrator |
| TD-010 | Policy layer не доведен до machine-readable parity с researcher-core | `config/strictness_profiles.json`, `bucket_contracts.json`, `claim_state_machine.json`, `skills_registry.json` | high | 2026-09-07 | code-orchestrator |
| TD-011 | Router contracts дублируются между JSON/TS/docs | `config/*.json`, `plugins/tool-skill-contract-router.ts`, `ROUTER_HOOKS_AND_TEMPLATES.md` | high | 2026-09-14 | code-orchestrator |
| TD-012 | Memory policy не имеет schema/storage contract | `MEMORY_POLICY.md`, future memory registry | medium | 2026-09-21 | code-orchestrator |
| TD-013 | Guard degradation matrix не формализован по strictness profiles | `config/guard_policy.json`, future strictness profiles | high | 2026-09-14 | code-orchestrator |
| TD-014 | `MANIFEST.md` counts/critical inventory устаревают после каждой волны | `MANIFEST.md` | low | 2026-09-07 | code-orchestrator |

Правило: каждый новый TD должен ссылаться на источник (аудит, ревью, FMEA, triz_critic).

## 4. Workflow

Статус на 2026-08-31: TD-009 частично снят на уровне bundle — runtime импортирован в `doc_Opencode_agern/shared` и `doc_Opencode_agern/scripts/code-factory`, но live OpenCode ещё не переключён на module-owned runtime.

1. **Создать** долг: code-orchestrator или code-reviewer добавляет запись в `config/tech_debt.json` + пишет в Global Kanban (`phase=tech_debt`).
2. **Оценить** `cost_if_delayed`: что ломается, если откладывать (блок фичи, рост coupling, риск инъекции).
3. **Запланировать** `sunset_at` или `review_trigger` — что наступит раньше, то и триггер.
4. **Отработать**: воркер правит по `acceptance`, тестер прогоняет acceptance command, ревьюер проверяет.
5. **Закрыть**: статус `done` + запись в `GLOBAL_TASK_CONTROLLER.md` / kanban + пост-анализ: почему долг возник (архетип).

Запрещено: закрывать долг без acceptance команды; держать `critical` дольше одного спринта без эскалации.

## 5. Связь с трекерами

- **Global Kanban** (`references/global-kanban/global_kanban.py`) — оперативный статус: `gk.report('code-factory','TD-001','tech_debt','WORKING','fix','1/3','патч _runner.py')`.
- **WP-0…WP-4** (`references/agent-kirpichik/wp-*.md` + `workspace/агент кодер`) — структурные долги фундамента (WP-0) блокируют все остальные WP.
- **TRIZ** — долги с kind `architecture|contradiction` обязательно проходят через `triz_critic` 6 чеков.
- **Guard** — долги с kind `security` не закрываются без `doc_guard` PASS.

## 6. Definition of Done для техдолга

Долг считается закрытым только если:

- [ ] `acceptance` команда выполнена (py_compile / schema check / smoke test) с логом.
- [ ] Нет хардкодов/секретов в измененных файлах (secret scan).
- [ ] Обновлены `MANIFEST.md`, `TOOL_SKILL_CONTRACT_AUDIT.md` если менялся контракт.
- [ ] Запись в kanban переведена в `DONE` с сообщением.
- [ ] Пост-анализ: добавлен пункт в `references/agent-kirpichik/ARIZ_LIGHT_METHOD.md` или `CODER_DESIGN_PRINCIPLES.md` если паттерн повторяется.

## 7. Команды

```powershell
# создать реестр если нет
if (-not (Test-Path "E:\Documents\Документы\doc_Opencode_agern\config\tech_debt.json")) { New-Item -ItemType File -Path "E:\Documents\Документы\doc_Opencode_agern\config\tech_debt.json" }

# проверить долги с просроченным sunset
python -c "import json,datetime,pathlib; p=pathlib.Path(r'E:\Documents\Документы\doc_Opencode_agern\config\tech_debt.json'); d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'debts':[]}; print([x['id'] for x in d['debts'] if x['status']=='open'])"

# отчитаться в kanban
python -c "import sys; sys.path.insert(0, r'Z:\server\.hermes\kanban'); from global_kanban import GlobalKanban; gk=GlobalKanban(db_path=r'E:\Documents\Документы\doc_Opencode_agern\.kanban.db'); gk.report('code-factory','TD-001','tech_debt','WORKING','fix','1/1','патч путей')"
```
