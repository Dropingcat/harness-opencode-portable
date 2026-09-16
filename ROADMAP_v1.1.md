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