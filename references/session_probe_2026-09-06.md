# Разведка старых сессий: внутренние диалоги агентов и всплывшие проблемы

Дата: 2026-09-06. Источник: `~/.local/share/opencode/opencode.db` (89 сессий, 4939 сообщений, 21390 частей).
Внутренние диалоги = `task`-вызовы (73 шт.) + локальные рассуждения (`reasoning`) оркестратора.

## Статус по найденному

### 🔴 Исправлено сегодня (в рамках этой работы)
1. **Attempt/rework state machine** — цитата подтверждена в `ses_f89be...` «Проверка рефакторинга writer-core»:
   2×REQUEST_CHANGES сжигали 2 из 3 attempt. Фикс: `rework_rounds`, попытка тратится только на реальную сдачу воркера.
2. **Multi-reviewer gate last-write-wins** — обнаружено в build-сессии 2026-09-06 14:11 («если первый REQUEST_CHANGES, второй APPROVE — gate перезапишется APPROVE»).
   Воспроизведено на живом коде: модуль с RETRY молча проскакивал. Фикс: fail-closed агрегация (worst-of), gate RETRY больше не затирается APPROVE другого модуля.

### 🟡 Актуально (не исправлено, рекомендации)
3. **Reviewer scope creep** — ревьюеры тащат расширенный DoD вместо скоупа задачи.
   ▶ **Исправлено 2026-09-06:** контракт ревьюера в `code-orchestrator.md` требует `scope_declared` + `out_of_scope_gaps[]`; `contract_validator.py` валидирует эти поля (комментарий вне scope → в out_of_scope_gaps, а не в comments); ревью всегда дельтой (код модуля + diff).
4. **Неконвергенция ревью-цикла** — r3_validators: 8 ре-ревью подряд.
   ▶ **Исправлено 2026-09-06:** детерминированный `tribunal_required` в редьюсере (после ≥2 review-фейлов модуля без PASS) выставляется кодом и выдаётся в `factory_ctl submit`/`status`; оркестратор ОБЯЗАН диспатчить аудитора (правило в промпте), флаг сам снимается при PASS. Тесты: `test_unresolved_module_marked_for_tribunal`, `test_tribunal_flag_clears_after_pass`.
5. **Огромные контексты оркестратора** — max 207,137 токенов; ре-ревьюеры тянут полную историю.
   ▶ **Обработано 2026-09-06:** правило «ре-ревью дельтой» закреплено в `code-orchestrator.md`; оставшаяся рекомендация (ужесточить compaction.tail_turns) требует ручного решения пользователя.
6. **Среда/потеря воркспейса** — сессия «Тест»: окружение writer-core оказалось reset.
   ▶ Не исправлено (требует ручного решения/политики snapshot).

### 🟢 Работает как задумано (подтверждено из сессий)
- Fail-closed guard: инъекция в БД → `P0 PASS`, `P2 FAIL` (провайдер дёрнут) → BLOCK; benign → PASS.
- Contract валидатор отсекает BOM/невалидный JSON.
- Каноническая цепочка `worker → reviewer REQUEST_CHANGES → APPROVE → PASSED → DONE` проходит в бою.

## Метрики разведки (маркеры в рассуждениях/сообщениях)
- attempt/popытки: 252 | REQUEST_CHANGES: 91 | rework: 177 | BLOCK/INVALID: 114 | retry/timeout: 92
- ошибка/не удалось: 99 | лимит/бюджет: 85 | контекст/truncation: 155 | файл не найден: 45
- завис/ожидание: 136 | дубль/повторное: 164

## Решения, принятые в этой сессии по итогам разведки
- Введён регрессионный тест `test_mixed_review_verdicts_aggregate_fail_closed` (+17 tests all green).
- Введён тест `test_batch_review_retries_do_not_burn_attempt` (неконвергенция REQUEST_CHANGES).
- Обновлён `code-orchestrator.md` (семантика attempt, пример диспатча при 2 REQUEST_CHANGES).
- **Изоляция Python (#7):** `.venv` (stdlib-only), `requirements-core.txt` + `requirements-mcp-doc.txt`, `setup_env.ps1`→`.venv`, `.gitignore`. Полный отчёт: `PYTHON_DEPENDENCIES.md` + `легаси/PYTHON_DEPENDENCIES_FINDINGS.md`.
- **Защита кода (#6):** git-коммит-гейт в `factory_ctl submit` (worker), шаблон `references/handoff-template.md`, правило «Безопасность работы» в промпте.