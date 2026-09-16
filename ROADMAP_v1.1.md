# Roadmap v1.1 — агенты, динамические промпты, память, контракты

Цель: превратить v1 (детерминированный роутинг) в **полную интеграцию агентов в работу
через OpenCode Desktop**: субагенты видны и вызываемы, их промпты динамически собираются
из контекста сессии, память harness-а питает промпты, а контракты между ролями
валидируются автоматически.

Полный реестр долгов и обоснование: см. `TECH_DEBT_AGENTS.md`.

---

## Версии

| Версия | Тег | Содержимое |
|---|---|---|
| v1 | `v1` | Native plugin + 15 ролей-спецификаций + runtime policy + MCP + bootstrap |
| v1.1 | *(не создан)* | Субагенты OpenCode, динамические промпты, память, контракты, native guard |

---

## Фаза 1 — Агенты OpenCode

- [ ] **A1**: генератор `scripts/agent_gen/gen_agents.py` — конвертация `agents/*.md` → `.opencode/agent/*.md`
  (frontmatter: `description`, `mode: subagent`, `tools`, `model`, `temperature`; тело — промпт роли).
- [ ] **A2**: `config/agent_gen.json` — маппинг «роль → модель» из `config/providers_auth`, правила frontmatter.
- [ ] **A3**: `harness_run` возвращает `agent_hint: {agent, model, prompt_template}`.
- [ ] **A4**: bootstrap шаг: запуск `gen_agents.py` после сборки; проверка «агенты видны в Desktop».
- [ ] **A5 (TD-A4)**: в `code-orchestrator.md`/`coder-worker.md` — обязательный шаг 0-ритуала старта:
  сверка с наличием git-репо (`git rev-parse`), при отсутствии — создание принимающей директории
  и оформление её как репо по всем правилам (git init + `.gitignore`, трекер, `MAP.md`, `README.md`,
  архитектурные файлы из `templates/`), фиксация базового среза коммитом до правок кода.

## Фаза 2 — Динамические промпты + контракты

- [ ] **I1**: `templates/agent_prompts/*.md` — шаблоны с плейсхолдерами
  (`{task} {workspace} {route} {capsules} {tools} {memory_context} {contracts}`).
- [ ] **I1a**: `config/agent_prompt_bindings.json` — роль → шаблон, правила подстановки, fallback.
- [ ] **I3**: `config/role_contracts/*.json` — интерфейсы роль→роль (вход/выход/обязательные поля/инварианты).
- [ ] **I4**: `harness.dispatch` — метод bridge: роль + входной контракт → дочерняя сессия
  → валидация результата по контракту → `structured_output`.
- [ ] **I1b**: Core: подстановка контекста в промпт перед диспатчем.

## Фаза 3 — Память + guard

- [ ] **I2**: портировать `scripts/memory/` (session_memory); хранилище `.runs/memory/*.json` (git-ignored).
- [ ] **I2a**: Core: read memory (по bucket/route/капсуле) → inject в промпт.
- [ ] **I2b**: Core: write memory после диспатча (что решено, какие контракты закрыты).
- [ ] **I5**: native guard: `tool.execute.before` → `guard/src/session_guard.py` для untrusted
  (webfetch, searxng_search, doc_extract) с кэшем скоринга.
- [ ] **P3**: live-сертификация `semantic.execute` → `HARNESS_SEMANTIC_ENABLED=1`.

## Фаза 3a — Трибунал (live-версия)

- [x] **T1 (P0)**: портировать `scripts/jobs/job_ctl.py` + зависимости; проверить импорт
  `tribunal_live_dialogue` на чистом клоне (без исходника рядом). *(закрыто в v1.0.1-commit: job_ctl.py перенесён, трибунал импортируется из чистой репы)*
- [ ] **T2 (P4)**: мигрировать `SubprocessJsonProviderTransport` → дочерняя сессия OpenCode
  (`semantic.execute` / `harness.dispatch`).
- [ ] **T3 (P4)**: судьи трибунала — изолированные дочерние сессии (parent/child), `TribunalExecutionEnvelope`
  как контракт, ответ через `DDC/DQC admission`.
- [ ] **T4**: `tribunal-judge` в генераторе `.opencode/agent/*.md`; `harness.dispatch` поддерживает
  `tribunal.role.execute`.
- [ ] **T5**: зарегистрировать живого провайдера «OpenCode Desktop agent» с
  `execution_capability: tribunal.role.execute`; связать с `semantic.execute`/`harness.dispatch`.
- [ ] E2E: live-трибунал (5 ролей) через Desktop, ответ проходит детерминированный admission.

## Фаза 3b — Сверка с документацией «миграция в плагин» (TD-D*)

- [ ] **D1**: портировать `scripts/writer/`, `scripts/capsules/`, `scripts/memory/`, `scripts/kanban/`,
  `shared/` (или явно задокументировать исключение из v1).
- [ ] **D2**: свести `health_check.py` → `doctor.py` как единый health-инструмент с живыми probes
  (bridge.hello, harness.status, capability snapshot, semantic provider readiness).
- [ ] **D3**: задокументировать `register_plugin.py` как временный project-scoped helper;
  канонический путь — bootstrap + `.opencode/opencode.json`.
- [ ] **D4**: зафиксировать расхождение capability hash в документации (f9de81 ≠ 60105d).
- [ ] **D5**: перенести bridge-тесты; добавить cancel/timeout E2E.
- [ ] **D6**: пометить CLI-лаунчеры `transport=opencode_cli_legacy`; не мигрировать до P5.
- [ ] **D7**: добавить smoke-тест `job_ctl` + документация host_ref mapping.
- [ ] **D8**: привести `compatibility/opencode/*.json` к шкале `TEST_AND_EVIDENCE_MATRIX.md`
  (`LIVE_CERTIFIED` только после live P2 gate).
- [ ] **D9**: сгенерировать `MANIFEST.json` + `SHA256SUMS.txt` + `decision_aliases.json`.
- [ ] **D10**: validation «snapshot ↔ schemas» в `compile_runtime.py --check`.

## Фаза 4 — Стабильность

- [ ] Перенести `tests/` плагина (7 файлов) и адаптировать под v1.1.
- [ ] E2E: research → tribunal → synthesizer через Desktop с субагентами.
- [ ] `docs/AGENTS_INTEGRATION.md`.

---

## Критерии готовности v1.1

1. 15 субагентов видны в Desktop и исполняются с ролевыми промптами.
2. `harness.dispatch` валидирует контракт на входе и выходе.
3. Память читается и пишется; контекст попадает в промпты.
4. Guard-гейт закрывает untrusted-инструменты.
5. `doctor.py` + `health_check.py` — HEALTHY; bridge smoke green.
6. Модули Writer/capsules/memory/kanban/shared либо перенесены, либо явно исключены (TD-D1).
7. `health_check.py`/`doctor.py` — единый doctor с живыми probes (TD-D2).
8. CLI-лаунчеры явно помечены legacy fallback (TD-D6).
9. `MANIFEST.json` + `SHA256SUMS.txt` присутствуют (TD-D9).
10. Совместимость с документацией: capability hash расхождение зафиксировано (TD-D4),
    compatibility-записи приведены к строгой шкале evidence (TD-D8).
11. Кодер при старте задачи сверяется с git-репо; при отсутствии создаёт принимающую
    директорию и оформляет её по всем правилам (git, трекер, карта, README, архитектурные
    файлы) до первой правки кода (TD-A4).