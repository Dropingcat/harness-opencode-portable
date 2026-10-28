# АУДИТ ПОЛНОТЫ И НЕПРОТИВОРЕЧИВОСТИ МАСТЕР-ПЛАНА МИГРАЦИИ

**Дата:** 2026-10-04
**Аудитор:** code-auditor (процессный/архитектурный аудит)
**Объект:** `E:\opencode_harness_portable\docs\PLAN_MASTER_MIGRATION.md` (266 строк)
**Сопоставлено с:** реальная ФС portable, легаси-документация `E:\Documents\Документы\doc_Opencode_agern-new`, трекеры долгов, `config/tech_debt.json`.
**Метод:** чтение реальных файлов (не выдумывание). Каждая строка ниже либо подтверждена чтением, либо помечена `[UNVERIFIED]`.

---

## СЕКЦИЯ 1. Реестр потерь (что в ФС есть, в плане НЕ упомянуто)

### 1.1 Каталоги верхнего уровня portable, отсутствующие в мастер-плане

| Сущность (путь) | Важность | Статус в плане | Рекомендация |
|---|---|---|---|
| `compatibility/1.18.30.json` + `1.18.16.json` | **Критично** | НЕ упомянут | Зависимость от живого движка opencode 1.18.30: миграция БЕЗ этого движка невозможна. Внести в B1-T2 (ядро) как предусловие; проверить актуальность после миграции (`check_evidence_levels.py`) |
| `compatibility/` каталог | Критично | НЕ упомянут | Сам каталог — артефакт сертификации движка (TD-D8/TASK_TREE 2.7). Нужен в B1 (структура) + гейт |
| `deploy/bootstrap.ps1` / `bootstrap.sh` / README | Критично | Упомянут косвенно (M0-a: якорь HARNESS_ROOT, junction shared, project-scope opencode.json) | Мастер-план указывает M0-a как «ГОТОВО», но артефакты (bootstrap.ps1, docs/DIAGNOSTICS_E2E.md) существуют. Зафиксировать явно в B1/B2 список артефактов Слоя 0 |
| `guard/docs/*.md` (ARCHITECTURE, THREAT_MODEL, TRIZ_*) | **Высокая** | НЕ упомянуты | Документация guard содержит требования (threat model, adversarial, TRIZ). Часть должна стать `shared/*.md` или canon. Внести в B1-T4 (shared diff) или W12 |
| `mcp/launchers/` (6 файлов) + `opencode_code_worker.py` | **Критично** | НЕ упомянуты | Launchers — единственный рабочий CLI-путь диспатча субагентов (TD-D6: transport=opencode_cli_legacy). M1/EXP-0/EXP-5 неявно зависят. Внести в W3/W11 или W12 (как legacy fallback). НЕ вошли в `scripts/` sync-группы B2-T1? (B2-T1 группы: scripts/agents/shared/plugins/skills/config/guard/hooks — mcp НЕ в списке!) |
| `hooks/coder-dom-verify.sh` | Критично | Упомянут только в W1 (pre-push) как существующий | Файл уже есть в portable, но не входит в sync-группы B2-T1 (нет группы `hooks`? — есть!). Уточнить B2-T1: группа `hooks` покрывает `coder-dom-verify.sh` |
| `runtime/` (registry.py, model_bindings.json) | Средняя | НЕ упомянут | runtime/registry.py используется compile_agents (B4-T7). `model_bindings.json` — маппинг модель/провайдер (TD-A3). Внести в W3/W5 |
| `templates/` (coder-dom.yaml, writer-dom-dissertation.yaml, adr-template, component-spec) | Средняя | НЕ упомянуты | `coder-dom.yaml` — целевой артефакт Coder DOM (TD-076, B4-T7/pre-push). templates/adr — процессные артефакты. Внести в B1 (структура) + W12 |
| `skills/opencode-current/*` (~130 скилов) | Низкая (вне скоупа) | НЕ упомянуты | Полный набор скилов — контент, не миграция. Маркировать «вне скоупа» |
| `tests/` (44 файла) | Высокая | НЕ упомянуты | В плане есть только B4-T11 (test_e2e_orchestration.py), EXP-2 фикстуры, M2. НЕ перечислены: tests/coder/* (139 тестов bridge), test_agent_gen, test_health_doctor, test_module_porting, test_route_duplication и др. — это регрессионная база. Внести в B5 (приёмка) явный список тестовых наборов, которые должны пройти |
| `scripts/ci/*` (test_integration, test_mcp_servers, test_chromadb) | Средняя | НЕ упомянуты | MCP/интеграционные тесты. Внести в B5/W5 |
| `scripts/research/*` (52 файла, включая 30+ тестов) | **Высокая** | НЕ упомянуты | План игнорирует research-контур (run_research.py, techdebt_control.py, тесты). Часть НЕ в portable? — НО листинг показывает scripts/research полный в portable. W10 (самообучение) ссылается на факты, но не на перенос research. Решение: маркировать «вне скоупа миграции» ИЛИ добавить в W12 (аудит цепочек research) |
| `scripts/researcher/` (64 модуля, 218 функций — PORTED по PORTABLE_DELTA) | Высокая | НЕ упомянуты | Researcher-ядро ПОРТИРОВАНО и есть в portable (r0/, tribunal_*, budget, policy). План молчит. Внести в B1 (структура) как факт + W12 |
| `scripts/glossary/*` (16 файлов) | **Критично** | Упомянут только B4-T6 (7 хардкодов glossary), B4-T7 (compile_agents) | НЕ упомянуты: coder_dom_build.py, verify_coder_dom.py, coder_dom_stub_gate.py (используются pre-push W1!), sync_tech_debt.py, tech_debt_cli.py (TD-137), compare_trees.py. Внести в B1/B5 + связать с W1/pre-push |
| `scripts/meta/` (СЕЙЧАС: только perfectionist.py + sleep_integration.py) | **Критично** | B1-T3 + W7 ПОКРЫВАЮТ (перенос 27 файлов) | ПОДТВЕРЖДЕНО: в portable только 2 файла. План корректен. НО: `PLAN_W1_GIT_HOOKS.md` §3.2 предупреждает, что до B1-T3 pre-commit будет печатать «perfectionist skipped» (skill_master отсутствует) — это согласованный риск, отражён |
| `scripts/jobs/job_ctl.py` | **Критично** | НЕ упомянут | job_ctl — рантайм Job/Attempt (TD-T1/TD-T7). В portable есть. B2-T1 sync-группы включают scripts/, но мастер-план не называет job_ctl. Внести в B1 (структура) + W6 |
| `scripts/tools/agent_loop.py` | Критично | B4-T5 ПОКРЫВАЕТ | Корректно |
| `scripts/tools/*` (остальные: session_analyzer, tech_debt_cli, gh_debt_*, chroma_indexer, gost_collector и др.) | Средняя/высокая | Частично (session_analyzer — W10; sync_tech_debt — B4-T6) | gh_debt_* (TD-144/145), chroma_indexer (TD-104 закрыт), gost_collector (TD-165). Внести в W12 как реестр, иначе «мёртвый код» |
| `scripts/orchestration/character_sheet.py`, `delegation_score.py` | Критично | M2 ПОКРЫВАЕТ (штраф solo) | Корректно. НО в W2 (оркестраторы) не упомянуты kanban_report/idle_tasks как ФАЙЛЫ — упомянуты. ОК |
| `scripts/memory/` (memory_bridge.py, memory_router.py) | **Критично** | B1-T3/W7 упоминают memory_bridge (п.6 PLAN_W7); W6 упоминает memory_router | ПОДТВЕРЖДЕНО: в portable scripts/memory есть оба файла (листинг). TD-175 (memory-router) отражён в PLAN_TD174-177. ОК |
| `config/` (58 файлов) | Критично | Частично | НЕ упомянуты: `memory_l1/l2/l3_policy.json` (TD-175), `tribunal_*.yaml` (трибунал), `routes_authority.json`, `skill_capsule_policy.json`, `runtime_source_manifest.json`, `capsule_*` и др. Большинство — уже в portable и мигрируют «как есть» через B1-T2 (ядро) / B2 (sync config). НО план не перечисляет НОВЫЕ конфиги: `feature_flags.json` (из REFACTOR_REVIEW), `anti_patterns_catalog.yaml` (из REFACTOR_REVIEW §8), `agent_prompt_bindings.json` (TD-I1), `role_contracts/` (TD-I3). Внести в B1/W7/W12 |
| `.github/workflows/ci.yml` | **Критично** | НЕ упомянут | CI-пайплайн (запуск pytest, компиляторов). Миграция должна проверить, что CI работает на portable. Внести в B5 (приёмка) |
| `MANIFEST.json`, `SHA256SUMS.txt` (генератор `gen_manifest.py`) | Высокая | НЕ упомянуты | Инвентарь дерева (TD-D9). После миграции перегенерировать. Внести в B5 |
| `AGENT_REPO_ACCESS.md` | Низкая | НЕ упомянут | Инфо-документ (GitHub доступ). Вне скоупа |
| `ROADMAP_v1.1.md` | Низкая | НЕ упомянут | Дорожная карта v1.1 (TECH_DEBT_AGENTS §4). Актуализировать после миграции. Вне скоупа |

### 1.2 «Потерянные» артефакты, критичные для миграции (сводка)

1. **`scripts/jobs/job_ctl.py`** — критичный рантайм (TD-T1). НЕ назван в плане. ⚠️
2. **`compatibility/` + движок 1.18.30** — предусловие миграции. НЕ назван. ⚠️
3. **`mcp/launchers/`** — единственный CLI-диспатч (TD-D6). НЕ назван. ⚠️
4. **`tests/` (44 файла)** — регрессионная база. НЕ названа как набор. ⚠️
5. **`scripts/glossary/*`** (coder_dom_build, verify_coder_dom, stub_gate) — используются pre-push W1. НЕ названы. ⚠️
6. **`config/feature_flags.json`, `anti_patterns_catalog.yaml`** — требования REFACTOR_REVIEW §4/§8. НЕ в плане. ⚠️
7. **`.github/workflows/ci.yml`** — CI. НЕ в плане. ⚠️
8. **`scripts/tools/gh_debt_*`** — TD-144/145 auto-фиксация долгов. НЕ в плане.
9. **`scripts/research/*` и `scripts/researcher/*`** — целые контуры. НЕ в плане (кроме W10 фактов). 📦 маркировать «вне скоупа» или W12.
10. **`shared/`** — в portable ТОЛЬКО 2 файла (harness-dispatch-map.md, search-depth-contract.md). B1-T4 говорит «9 недостающих файлов + route-preflight.md» — ПОДТВЕРЖДЕНО нехваткой. ОК.

---

## СЕКЦИЯ 2. Реестр легаси-документов (E:\Documents)

| Документ | Тема | Релевантность | Отражён в плане | Пробел |
|---|---|---|---|---|
| `docs/REFACTOR_PLAN_2026-09-22.md` | V-архитектура V1-V8, V-1 Health Monitor, 51 TD | **Высокая** | ДА — W7 (V1-V8, ночной прогон), B1-T3 (перенос meta), RUD-1 (канон→legacy) | **Пробел А:** Health Monitor (V-1) — в плане только «V1–V8» и «ночной прогон», НЕ описаны 5 каналов, право вето, реанимация (это в PLAN_W7_B1T3 §1.2). **Пробел Б:** Feature Flags (REFACTOR_REVIEW §4: debt_driven_cycle_enabled, trace_store_enabled, meta_validator_enabled) — НЕ в плане. **Пробел В:** стратегия миграции (Parallel Run / Gradual Rollout / откат) — НЕ в плане |
| `docs/META_CYCLE_CONSOLIDATED_2026-09-30.md` | Контракты Meta-Cycle (Pydantic), инварианты | **Высокая** | ДА — W7, B1-T3 (перенос 27 файлов подтверждён листингом: сейчас в portable только 2) | Пробел: не сказано, какие из 28 py-файлов meta НЕ реализованы (state.py, branch.py, legacy.py, aar.py, orchestrator.py — «в разработке»). План молчит о статусе «в разработке» — кодер перенесёт полуфабрикаты как есть (риск!). Отражено в PLAN_W7 §1.1 как «переносится как есть» — это СОЗНАТЕЛЬНО, но мастер-план не фиксирует |
| `docs/token-consumption-analysis.md` | Бюджет токенов, 7 путей экономии, метрики | **Средняя** | НЕ отражён | **Пробел Г:** бюджетные лимиты (max_hops=3, max_nodes=15, max_tokens=40000, cache hit >10, LLM calls/claim <0.7, compaction <2) НЕ перенесены в план. W10 (самообучение) — анализ, НЕ бюджет. Модуль `budget.py` (в portable scripts/researcher/budget.py ЕСТЬ) — но контракт бюджета для миграции не задан. НЕ блокирует миграцию, но нужно в W12 |
| `docs/ENV_VARIABLES.md` | Переменные окружения (GITHUB_TOKEN, OPENCODE_HARNESS_ROOT, RESEARCH_*) | **Высокая** | ДА — B3 (env), B4-T2 (пути) | Пробел: W12 NEW-6/NEW-7 (env-контракты research/writer) отражены; но список переменных (RESEARCH_RUNNER_SH, RESEARCH_RULES_PATH) и правило «секреты только в .env» — НЕ в плане. Маркировать как canon для B3 |
| `docs/PLAN_W7_B1T3_META_CYCLE_PORTING_2026-10-04.md` | Перенос meta в portable: 27 файлов, граф импортов, ночной прогон, интеграция | **Высокая** | ДА — B1-T3, W7 (ссылка в разделе 9) | **Пробел Д:** мастер-план НЕ содержит: (1) точный список 27 файлов (в PLAN_W7 есть); (2) проверку импорта 29 модулей; (3) meta_nightly.cmd/XML; (4) текст секции «Meta-Cycle health (V-1)» для code-orchestrator.md. Всё это — в детальном плане. НЕ потеряно, но мастер-план отсылает, не дублируя. Это ОК для «единого документа»? — НЕТ, для передачи кодеру нужно явно указать «детальный план — источник исполнения» |
| `docs/REFACTOR_REVIEW_2026-09-30.md` | DoD, тесты, миграция, Pydantic-контракты, антипаттерны, +15 TD | **Высокая** | Частично — W7, V1-TD-* в tech_debt.json | **Пробел Е:** DoD по этапам (Этап 0-2), план тестирования (3 уровня), anti_patterns_catalog.yaml, MEAL-инварианты — НЕ в мастер-плане. Anti-pattern каталог — новый артефакт, должен быть в B1/W7 |
| `docs/core-chain-status-and-debt-review.md` | Researcher-core цепочка, R0-S упрощения, token budget prod | **Средняя** | НЕ отражён | Пробел: researcher-core (r0/, budget, policy, guard) — большой портированный контур. Мастер-план молчит. Маркировать «вне скоупа миграции» (уже в portable) |
| `docs/r0-simplification-tracker.md` | Осознанные упрощения R0-S | Средняя | НЕ отражён | Тот же контур. Вне скоупа |
| `docs/soft-harness-testing.md` | Детерминированный локальный цикл без LLM | Средняя | НЕ отражён | Пробел: принцип «детерминированный локальный loop прежде субагентов» — НЕ сформулирован в плане. Это архитектурный инвариант. Добавить в принципы плана (раздел 1) |
| `docs/implementation-artifact-alignment.md`, `docs/scalable-architecture-seams.md`, `docs/artifact-gap-register.md` | Researcher-core порты/артефакты/gap-register | Низкая | НЕ отражены | Вне скоупа миграции (контур уже в portable) |
| `docs/LEGACY_CHATS_FEATURES_2026-09-30.md` | Фичи легаси-чатов | Низкая | НЕ отражён | Вне скоупа |
| `docs/ses_f37cd44a0ffe5vlOQMarL4Cew1.json` | Дамп сессии | Низкая | НЕ отражён | Мусор/артефакт. Вне скоупа |
| **Корень канона:** `TECH_DEBT.md`, `CURRENT_ARCHITECTURE.md`, `PROJECT_STATE.md`, `RUNTIME_*`, `RESEARCHER_R4_*` (20+ доков), `AGENT_ARCHITECTURE_PLAN_VS_FACT.md` и др. | Архитектура канона, R4-трибунал | Средняя | Частично (R4 → researcher-ядро в portable) | **Пробел Ж:** КАНОН-КОРЕНЬ содержит ~100 документов архитектуры (R4-трибунал, ROLE_CARD, SKILL_*, MEMORY_*). Мастер-план НЕ определяет их судьбу: canon → `docs/canon/` (46 файлов уже есть) / shared / legacy-архив. Решение: маркировать как «исторические источники», НЕ переносить, кроме: `MEMORY_POLICY.md` (→ shared), `SECURITY_GUARD.md` (→ guard/docs), `ROLE_CARD_PORTABLE_DOM_FUTURE.md` (→ shared) — кандидаты в shared/canon |
| `TECH_DEBT_AGENTS.md` (portable корень) | Техдолг v1→v1.1: агенты, TD-A*/I*/T*/D* | **Высокая** | Частично — TD-D1 (MODULE_PORTING_EXCLUSIONS), TD-D2 (doctor), TD-D8 (evidence levels) закрыты; TD-A3 (model binding) — B4-T7/W3 | **Пробел З:** TD-I1 (динамические промпты + agent_prompt_bindings.json), TD-I3 (role_contracts), TD-I4 (harness.dispatch), TD-I5 (native guard hook), TD-T1..T5 (трибунал live) — НЕ в мастер-плане. W11 (универсальный агент) частично покрывает (shim, serve, MCP), но НЕ harness.dispatch (TD-I4). Это ЗНАЧИТЕЛЬНЫЙ пробел для «полноты» |
| `DEVELOPMENT.md` (portable корень) | Git Flow | Низкая | НЕ отражён | Процессный документ. Вне скоупа |

---

## СЕКЦИЯ 3. Инвентаризация трекеров + схема глобального файла долгов

### 3.1 Таблица трекеров

| Трекер | Что отслеживает | Открыто | Связан с мастер-планом |
|---|---|---|---|
| `config/tech_debt.json` (portable) | 236 записей (open 177): TD-*, CD-*, WR-*, RS-*, V*-TD-*, E2E-01..07 | 177 | ДА: B4-T6 (пометить history), RUD-8 (E2E-01..07 зарегистрированы, строки 4288-4455, sunset 2026-10-16). **ПОДТВЕРЖДЕНО чтением** |
| `docs/TRACKERS/TECH_DEBT_MASTER.md` (portable) | 229 записей (open 170), префиксы CD/WR/RS/PL/TD/V*-TD-* | 170 | НЕ связан — НЕТ поля plan_block; дублирует tech_debt.json частично. Статус «Активные» — срез 2026-10-01 |
| `docs/glossary/IMPLEMENTATION_STATUS.md` | Функции IMPLEMENTED/PARTIAL/CONTRACT_ONLY/DEFERRED по патчам | — | НЕ связан. Устарел (2026-09-18, до E2E) |
| `docs/glossary/PORTABLE_DELTA.md` | 40 модулей/90 функций отсутствуют в portable | — | СВЯЗАН: список отсутствующих = кандидаты переноса; B2-T4 (scripts/writer), B1-T4 (shared), W12 (registry пустых интеграций) |
| `packages/opencode-harness-plugin/TASK_TREE.md` | P1-P6 плагина | 4.6, 4.7, 5.5, 6.5, 6.7, 7.1-7.3, 8.x open | НЕ связан. P5/P6 (convergence, certification) — кандидаты в W12 |
| `packages/opencode-harness-plugin/P1_STATUS.md` | P1+P2+P3 статус | semantic NOT_CERTIFIED | НЕ связан. P3-сертификация — блокер W11/W5 (EXP-4/EXP-5) |
| `docs/MODULE_PORTING_EXCLUSIONS.json` | Исключения переноса (writer, kanban, memory, capsules, shared) | — | СВЯЗАН: B2-T4 (scripts/writer), B1-T4 (shared) |
| `TECH_DEBT_AGENTS.md` (portable) | TD-A*/I*/T*/D* (агенты, интеграция, трибунал) | TD-A3 частично, TD-I1..I5, TD-T1..T5, TD-D6 | ЧАСТИЧНО (см. Пробел З) |
| `docs/PLAN_TD174-177_FACTORY.md` (portable) | TD-174..177 + M0 meta-portable | M0-M4 планы | ЧАСТИЧНО: TD-174 (supervisor) — НЕ в мастер-плане; TD-175 (memory-router) — W6; TD-176 (router-hints) — W5/W12; TD-177 (context-skill) — W12 NEW-1. **Пробел И:** TD-174 (agent_supervisor.py, .tmp_l2.json) НЕ упомянут в мастер-плане, хотя B4-T8 (idle_tasks создаёт .tmp_l2.json) ссылается на него косвенно |
| `docs/PLAN_E2E_MATRYOSHKA.md` (portable) | Слои 0-6, E2E-01..07 | — | ПОЛНОСТЬЮ свёрнут в план (M0-M6, Блок 6) — ПОДТВЕРЖДЕНО |
| `docs/PLAN_W1_GIT_HOOKS.md` (portable) | W1 хуки, merge m5/m6 | — | ПОЛНОСТЬЮ свёрнут в W1/M4 — ПОДТВЕРЖДЕНО |
| `docs/PLAN_W7_B1T3_..._PORTING` (канон docs) | W7 мета-цикл | — | ПОЛНОСТЬЮ свёрнут в W7/B1-T3 — ПОДТВЕРЖДЕНО |
| `docs/TRACKERS/TECH_DEBT_MASTER.md` (канон? — в portable есть) | — | — | См. выше |
| `tech_debt_current.json`, `TECH_DEBT_CURRENT.md`, `CLOSED_TECH_DEBT.md` (канон root «Документы для работы») | Исторический реестр | — | Источник миграции tech_debt.json (authority_note: «migrated from патчи/миграция/tech_debt_current.json (65 records)») — ПОДТВЕРЖДЕНО |

### 3.2 Схема глобального файла долгов с маркировкой по блокам

**Рекомендация:** расширить `config/tech_debt.json` полем `plan_block` (НЕ создавать отдельный файл — единый источник уже есть). Синхронизировать `docs/TRACKERS/TECH_DEBT_MASTER.md` как человекочитаемое представление с тем же полем.

```json
{
  "schema": "tech_debt/3.0",
  "note": "Добавлено поле plan_block: {block, sub, status_in_plan, priority}. plan_block=null → вне скоупа миграции.",
  "debts": [
    {
      "id": "TD-174",
      "title": "Оркестратор не аудирует суб-агентов во время их работы",
      "severity": "high",
      "owner": "code-orchestrator",
      "status": "open",
      "plan_block": {
        "block": "W4",
        "sub": "supervisor (TD-174)",
        "status_in_plan": "MISSING",
        "priority": "P1",
        "gap_note": "НЕ упомянут в PLAN_MASTER_MIGRATION.md — добавить W4-T2 (agent_supervisor.py)"
      }
    }
  ]
}
```

**Маппинг префиксов → блоки:**

| Префикс | Примеры | Блок/ветка плана | Статус |
|---|---|---|---|
| TD-001..TD-140 (порт/интеграция) | TD-003, TD-073, TD-109, TD-138 | B1/B4/W5/W12 | mapped |
| TD-141..TD-179 (порт/интеграция поздние) | TD-174, TD-175, TD-176, TD-177, TD-179 | W4/W6/W5/W12 | **TD-174, TD-179 НЕ mapped** |
| E2E-01..07 | — | M0-M6 (матрёшка) | mapped (RUD-8, строки 4288-4455) |
| V1-TD-01..08, V*-TD-NEW-* | — | W7 (V-архитектура) | mapped через W7/B1-T3, но V*-TD без plan_block в JSON |
| CD-*, WR-*, RS-* | RS-024 (крит. researcher), CD-004 | W12 / вне скоупа | Частично |
| TD-A1..A4, TD-I1..I5, TD-T1..T5, TD-D1..D10 (TECH_DEBT_AGENTS) | TD-I4, TD-T1 | W11/W12 | **TD-I4, TD-T1..T5 НЕ mapped** |
| TD-REF-01..30 (REFACTOR_PLAN) | TD-REF-04 (TraceStore) | W7 | mapped (через V*-TD) |
| R0-S001..S016 (r0-tracker) | — | Вне скоупа (researcher-core в portable) | вне скоупа |
| TD-D1..D10 (TECH_DEBT_AGENTS) | TD-D6 (launchers) | W12 | **TD-D6 НЕ mapped** |

---

## СЕКЦИЯ 4. Карта новой архитектуры

### 4.1 Целевая архитектура после миграции (текстовое дерево)

```
E:\opencode_harness_portable  (SOURCE OF TRUTH, канон после миграции)
│
├── [ЯДРО / CORE]
│   ├── opencode.json (portable: dist+venv, M0 project-scope)          B1-T2/M0-a
│   ├── HARNESS_ROOT (якорь)                                            M0-a
│   ├── compatibility/1.18.30.json  ← живой движок                      [ПРОБЕЛ: не в плане]
│   ├── runtime/ (registry.py, model_bindings.json)                     [ПРОБЕЛ: не в плане]
│   ├── .opencode/agent/ (26 сгенерированных агентов)                  B4-T7
│   └── venv/ (.venv, whitelist 62+ пакетов)                            B1-T1
│
├── [КОНТУРЫ / CONTOURS — детерминированные скрипты]
│   ├── scripts/meta/ (28 py: V1-V8, health monitor)                    B1-T3/W7
│   ├── scripts/code-factory/ (state_reducer, contract_validator,       [ядро фабрики, B4/B5]
│   │     provenance, semantic_transport, tribunal_trigger NEW)         W4/M3
│   ├── scripts/orchestration/ (kanban_report, idle_tasks, character)   W2/M2
│   ├── scripts/tools/ (agent_loop, sleep_git NEW, git_session_sync NEW,
│   │     session_analyzer, sync_tech_debt, tech_debt_cli)              B4-T5/W1/W10/B4-T6
│   ├── scripts/jobs/job_ctl.py                                         [ПРОБЕЛ: не в плане]
│   ├── scripts/memory/ (memory_bridge, memory_router)                  W6/TD-175
│   ├── scripts/agent_gen/ (compile_agents, gen_runners)                B4-T7/W3
│   ├── scripts/router/ (resolve_route, resolve_bundle, compile_runtime) W5
│   ├── scripts/researcher/ (64 модуля: tribunal_*, r0/, budget)        [вне скоупа/W12]
│   ├── scripts/research/ (52 файла, тесты)                             [вне скоупа/W12]
│   ├── scripts/writer-core/ (40 модулей)                               [вне скоупа/W12]
│   ├── scripts/glossary/ (coder_dom_build, verify, sync_tech_debt)     [ПРОБЕЛ: W1/pre-push]
│   ├── scripts/ci/ (test_e2e_*, test_mcp_servers)                      B5/M2
│   └── scripts/meta/sleep_integration.py (M5-M10 цикл сна)             W7/M4
│
├── [ОБВЯЗКА / PERIMETER]
│   ├── hooks/ (pre-commit, post-commit, pre-push, hook_utils,          W1/M4
│   │     coder-dom-verify.sh)   core.hooksPath
│   ├── mcp/ (academic_search, coder_router, doc_extract, searxng)      EXP-5/W11
│   ├── mcp/launchers/ (CLI-legacy диспатч, transport=opencode_cli_legacy) [ПРОБЕЛ: TD-D6]
│   ├── guard/ (src: session_guard, semantic_layer, adversarial_build)  B4-T2/W4
│   ├── packages/opencode-harness-plugin/ (harness_run/harness_status,  W5/W11/EXP-4
│   │     semantic.execute gated, bridge)                               M1
│   ├── shared/ (9 недостающих + route-preflight.md +                   B1-T4/B2-T4/M0-a
│   │     orchestration-thread-process.md, code-factory-process.md)
│   ├── skills/opencode-current/ (~130)                                 [вне скоупа]
│   ├── templates/ (coder-dom.yaml, adr-template)                       [ПРОБЕЛ: не в плане]
│   ├── config/ (58 JSON/YAML; + NEW: feature_flags, anti_patterns,     B1-T2/W12
│   │     agent_prompt_bindings, role_contracts)
│   ├── deploy/ (bootstrap.ps1)                                         M0-a
│   └── .github/workflows/ci.yml                                        [ПРОБЕЛ: не в плане]
│
└── [ДОКУМЕНТАЦИЯ]
    ├── docs/PLAN_MASTER_MIGRATION.md (этот)                            —
    ├── docs/canon/ (46 глав, ch13=«хуки»)                              W8/B4-T10
    ├── docs/glossary/ (function_index, GLOSSARY, IMPLEMENTATION_STATUS,
    │     PORTABLE_DELTA)                                               B4-T6
    ├── docs/TRACKERS/TECH_DEBT_MASTER.md → sync c tech_debt.json       [3.2]
    ├── docs/PLAN_*.md (E2E_MATRYOSHKA, TD174-177, W1, W7)              [источники]
    └── E:\opencode_harness\_LEGACY_ARCHIVE (reparse point)             B1-T5

Легаси-документы канона (REFACTOR_PLAN, META_CYCLE, R4-архитектура, TECH_DEBT_*):
  → docs/canon/ (избранное: ENV_VARIABLES, REFACTOR_PLAN как история) ИЛИ _LEGACY_ARCHIVE
  → shared/ (MEMORY_POLICY, SECURITY_GUARD, ROLE_CARD — действующие контракты)
  → остальное — legacy-архив (не переносить)
```

### 4.2 Таблица компонент → роль → статус в плане

| Компонент | Роль | Статус в плане |
|---|---|---|
| opencode.json portable | Ядро конфигурации (dist+venv, plugin) | B1-T2 — спека готова |
| venv | Рантайм-изоляция | B1-T1 — спека готова (whitelist) |
| scripts/meta/* (28) | Мета-цикл V1-V8 + V-1 Health Monitor | B1-T3/W7 — спека готова (детальный план W7) |
| agent_loop.py | Волновой цикл, авто-продолжение, флаги M6 | B4-T5 — спека готова (EXP-2 выполнен) |
| sleep_git.py / git_session_sync.py | Цикл сна M5/M6, гитификация | W1/M4 — перенос из веток m5/m6, спека готова |
| tribunal_trigger.py | Трибунал-триггер (аудитор) | W4/M3 — НОВЫЙ |
| peer_coordinator.py | Peer-координация deliberation | W9 — спека готова (T4 BLOCKED) |
| canon_loader/canon_search | FTS5-поиск по 46 главам | B4-T10/W8 — POST-миграция |
| session_analyzer/lesson_extractor/skill_promoter | Самообучение W10 | W10 — СПЕЦИФИКАЦИЯ ГОТОВА |
| shim opencode.cmd + opencode-ai | Универсальный агент (CLI-контур) | B3-T2/W11 — RUD-2 решён |
| harness_control_server.py (MCP) | API-контур (serve --port 4099) | W11-T2 — новый |
| sync_to_live.py | live-зеркало | B2-T1..T5 — частично (USER_DECISION) |
| setup_env.ps1/.sh | env-контракт | B3-T1/B4-T9 — готова |
| git-хуки (3+utils) | Гейты коммитов/push | W1/M4 — спека готова |
| job_ctl.py | Job/Attempt рантайм | **НЕ В ПЛАНЕ** ⚠️ |
| mcp/launchers/* | CLI-legacy диспатч субагентов | **НЕ В ПЛАНЕ** (TD-D6) ⚠️ |
| scripts/glossary/* | Coder DOM + гейты (pre-push) | **НЕ В ПЛАНЕ** (используется W1) ⚠️ |
| feature_flags.json / anti_patterns_catalog.yaml | Миграция V2/V3 | **НЕ В ПЛАНЕ** ⚠️ |
| tests/ (44 файла) | Регрессионная база | **НЕ В ПЛАНЕ** как набор ⚠️ |
| .github/workflows/ci.yml | CI | **НЕ В ПЛАНЕ** ⚠️ |
| tech_debt.json (+plan_block) | Единый реестр долгов | B4-T6/RUD-8 — расширить полем plan_block (3.2) |

### 4.3 Потоки данных / цепочки автоматики

Мастер-план НЕ содержит явных цепочек C1-C7 (grep подтвердил: термин «цепочки автоматики C1-C7» в плане отсутствует). Цепочки выводятся из веток:

```
W1 хуки:  commit → perfectionist(warn) + sleep_git(dry-run) → post-commit: compile_agents --check
          → health_check → session_sync --no-commit → pre-push: compile_agents(БЛОК) + coder-dom-verify
W2 ритуалы: старт (капсула → project_context → «Где я» → ROUTE preflight) →
          работа → закрытие (kanban_report → memory add → liveness)
W5 роутер: harness_run → resolve_route → bundle → runtime_snapshot.json → agent_hint
W7 мета-цикл: meta_daemon --once (HP/damage/veto) → ночь: sleep cycle → L2→L3 промоушен
W9 peer: detect → zone → claim → check (max_rounds=2) → эскалация → AMBIGUOUS
W8 canon: canon_loader → SQLite FTS5 → canon_search → docs/canon/46
W10 обучение: session_analyzer → lesson_extractor → skill_promoter → memory_integration
W11 агент: shim(CLI) / serve(API) / Desktop(GUI) → opencode-ai → MCP harness_control
W13 сон-git: sleep_git+диффы+merge-tree pre-check → sleep_report_check → meta_nightly
```

**РЕКОМЕНДАЦИЯ:** добавить в мастер-план раздел «Цепочки автоматики C1-C7» (или явно заявить, что C1-C7 — синоним W1-W13/M0-M6 и не вводить новую нотацию). Сейчас термин C1-C7 нигде не определён.

---

## СЕКЦИЯ 5. ВЕРДИКТ О ГОТОВНОСТИ К ПЕРЕДАЧЕ

### 5.1 Вердикт: **ДА, С УСЛОВИЯМИ** (условно готов к передаче кодеру)

### 5.2 Что блокирует (критические пробелы — закрыть ДО передачи)

1. **Целостность sync-групп B2-T1.** Группа `scripts/` неявно включает mcp/launchers, но мастер-план не называет `mcp/launchers/` и `scripts/jobs/job_ctl.py`. Без явного решения эти файлы либо потеряются при зеркалировании, либо останутся вне миграции.
2. **Порядок зависимости W1 ↔ B1-T3.** pre-commit вызывает `perfectionist` (импортирует `skill_master`, которого нет до B1-T3). В PLAN_W1 риск 6.1 задокументирован (warning-only), но в критическом пути (раздел 8) W1 идёт ПОСЛЕ B1-T3 — это корректно. НО в разделе 8 порядок: B1→B4→B3→W11→W1.. — B1-T3 выполняется в шаге 1, W1 в шаге 5 — OK. Снять риск.
3. **`compatibility/` и живой движок 1.18.30** — предусловие, НЕ названное в плане. EXP-5 (MCP на portable venv) требует живой движок.
4. **Критический путь не содержит явных гейтов для тестов.** B5 «6 команд E2E-приёмки» не перечисляет тестовые наборы (44 файла tests/). Кодер без списка не знает, что прогонять.
5. **Отсутствие решения по контурам research/researcher/writer-core.** В portable они ЕСТЬ и ПОРТИРОВАНЫ (PORTABLE_DELTA), но план молчит — кодер может «забыть» их проверить или случайно удалить при чистке. Нужна явная маркировка «вне скоупа, НЕ трогать» или задача W12.

### 5.3 Рекомендации перед передачей (приоритет)

**P0 (до передачи):**
1. Добавить в B1/B2 раздел «Инвентарь portable» со списком НЕ упомянутых сущностей (раздел 1 выше) и их судьбой: мигрировать / вне скоупа / legacy.
2. Явно перечислить `mcp/launchers/`, `scripts/jobs/job_ctl.py`, `scripts/glossary/*` в подходящих блоках (W3/W6/W1).
3. Зафиксировать в B5 полный список тестовых наборов (44 файла) и гейт `pytest` + `compile_runtime.py --check` + `compile_agents --check` + `check_*` (7 гейтов из TECH_DEBT_AGENTS: module_porting, plugin_registration, route_duplication, evidence_levels, health_canonical).
4. Добавить в раздел 1 (принципы): Feature Flags для V2/V3 (`feature_flags.json`), стратегию миграции (parallel-run/rollout/откат) — из REFACTOR_REVIEW §4, инвариант «детерминированный локальный loop» из soft-harness-testing.md.

**P1 (в процессе):**
5. Расширить `config/tech_debt.json` полем `plan_block` (схема 3.2) и синхронизировать `docs/TRACKERS/TECH_DEBT_MASTER.md`.
6. В W12 (аудит цепочек) добавить: TD-I4 (harness.dispatch), TD-T1..T5 (live-трибунал), TD-D6 (launchers), TD-174 (supervisor), TD-179 (agent_loop↔meta-cycle), RUD-2 остаток (P3-сертификация semantic.execute).
7. Определить судьбу канон-корня (~100 документов): избранное → docs/canon (ENV_VARIABLES, REFACTOR_PLAN как история), действующие контракты → shared (MEMORY_POLICY, SECURITY_GUARD, ROLE_CARD), остальное → _LEGACY_ARCHIVE.

**P2 (не блокирует):**
8. Токен-бюджет (token-consumption-analysis): контракт лимитов (max_tokens=40000, cache>10, calls/claim<0.7) — в W12.
9. `.github/workflows/ci.yml` — включить в B5 приёмку.
10. Зафиксировать в плане, что `scripts/research/`, `scripts/researcher/`, `scripts/writer-core/` — «вне скоупа миграции» (уже портированы), с проверкой их тестов в B5.

### 5.4 Самодостаточность

Отчёт основан на чтении: мастер-план (266 строк, полностью), PLAN_W1_GIT_HOOKS.md (438), PLAN_E2E_MATRYOSHKA.md (231), PLAN_TD174-177_FACTORY.md (40), PLAN_W7_B1T3 (489), TECH_DEBT_MASTER.md (245), TECH_DEBT_AGENTS.md (397), PORTABLE_DELTA.md (207), IMPLEMENTATION_STATUS.md (79), MODULE_PORTING_EXCLUSIONS.json (67), tech_debt.json (4462, включая строки 4288-4455 E2E-01..07), легаси REFACTOR_PLAN/META_CYCLE/token/ENV/REFACTOR_REVIEW/core-chain/soft-harness/r0-tracker/artifact-*/scalable-seams, листинги всех каталогов portable и канона.

**Не проверено (потребует исполнения/команд):**
- `[UNVERIFIED]` Список «14 файлов хардкодов канона» (B4-T6) — не перечитывал каждый (grep по канон-путям: `Get-ChildItem -Recurse *.md,*.py | Select-String -Pattern 'doc_Opencode_agern|E:\\Documents'`).
- `[UNVERIFIED]` Точный состав 9 недостающих shared-файлов (B1-T4) — сверка `diff shared/` канон vs portable: `git diff --no-index E:\Documents\...\shared E:\opencode_harness_portable\shared`.
- `[UNVERIFIED]` «46 файлов docs/canon» — фактически 42 (ch01..ch42 + appA/appB/appC = 45; план говорит 46). Расхождение на 1: проверить `Get-ChildItem docs\canon | Measure-Object`.
- `[UNVERIFIED]` «394/426 сессий opencode.db» (W10) — не пересчитывал БД: `python -c "import sqlite3; c=sqlite3.connect(r'<db>'); print(c.execute('SELECT count(*) FROM session').fetchone())"`.
- `[UNVERIFIED]` 62/76 пакетов venv (B1-T1) — не пересчитывал: `.venv\Scripts\pip.exe freeze | Measure-Object`.
- `[UNVERIFIED]` «26/26 DIFF» compile_agents (B4-T7) — команда из W1 §5.2.