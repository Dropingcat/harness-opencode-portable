# Runtime Launch Runbook

Последовательность запуска unified module на конкретной машине.

## 0. Windows: кириллический путь → ASCII junction

Реальный harness лежит в `E:\Documents\Документы\doc_Opencode_agern` (кириллица ломает консоль PowerShell cp1251 и subprocess).

Создан junction (Windows) — **ASCII-путь**:

```
E:\opencode_harness  →  E:\Documents\Документы\doc_Opencode_agern
```

- Все env-переменные используют `E:\opencode_harness\...` (ASCII).
- Плагин в `opencode.jsonc` тоже `file:///E:/opencode_harness/plugins/...`.
- Править только реальный кириллический каталог; junction автоматически отражает.

Пересоздать, если junction пропал:
```cmd
mklink /J "E:\opencode_harness" "E:\Documents\Документы\doc_Opencode_agern"
```

## 0. Требования

- Python 3.11+
- OpenCode installed (`opencode` в PATH или `OPENCODE_BIN`)
- Плагин `tool-skill-contract-router.ts` зарегистрирован в `opencode.jsonc` (уже сделано)

## 0.1 Guard (trust-boundary)

Guard вызывается из плагина (hook `tool.execute.after`) для untrusted tools через `guard_runner.py` (P0 + P2, fail-closed).

- P0 (`session_guard.py`) — сигнатурный, без сети, всегда.
- P2 (`semantic_layer.py`) — LLM-классификатор (cloud polza / local ollama).

**Ключ для guard (отдельный от основного):**
1. Никогда не класть в HARNESS/репо.
2. Задать один раз в user env:
   ```powershell
   $POLZA_GUARD_KEY = "your-separate-guard-key"
   [Environment]::SetEnvironmentVariable("POLZA_API_KEY", $POLZA_GUARD_KEY, "User")
   ```
   или раскомментировать в `scripts/setup_env.ps1`.
3. Конфиг guard — `C:\Users\Arhys\.config\opencode\guard_config.json` (вне HARNESS, key=None; ключ идёт через env).

Поведение: `PASS` — ок; `BLOCK/DEGRADED/FAIL` — блок (fail-closed). Модель начинает вызываться только при наличии `POLZA_API_KEY`.

## 1. Настроить окружение

### Windows
```powershell
powershell -ExecutionPolicy Bypass -File "E:\Documents\Документы\doc_Opencode_agern\scripts\setup_env.ps1"
```

### Linux/Pi
```bash
export OPENCODE_HARNESS_ROOT=/path/to/doc_Opencode_agern
source /path/to/doc_Opencode_agern/scripts/setup_env.sh
```

## 2. Проверить окружение

```bash
python scripts/validate_env.py
```

Ожидается `WARN` на missing research-скрипты (нормально, если research-контур не подключён).

## 3. Проверить готовность модуля

```bash
python scripts/health_check.py
```

Ожидается:
- Plugin Loaded: OK
- Guard Running: OK (via DOC_GUARD_ENTRYPOINT)
- MCP Servers: FAIL (пока серверы не запущены)
- DB Accessible: зависит от OPENCODE_SESSION_DB

## 4. Запустить MCP серверы (опционально)

```bash
python scripts/start_mcp_servers.py start
```

Только если нужны `coder_run`, `arxiv_search`/`openalex_search`, `extract_document`, `searxng_search` в OpenCode runtime.

## 5. Перезапустить OpenCode

После env + MCP — перезапуск OpenCode, чтобы:
- plugin перечитался
- MCP серверы появились в tool surface
- новые env vars подхватились

## 6. Проверка агентного блока

В TUI: `Tab` → должны быть видимы первичные агенты:
- `code-orchestrator`
- `research-orchestrator`
- `writing-orchestrator`

Запустить smoke: «implement hello world» через `code-orchestrator` → ожидать dispatch → factory_ctl → отчёт фабрики.

## 7. Research-контур (только если есть claimeai-service)

Если на этой машине есть `run_research.sh` и скрипты Hermes:
1. прописать RESEARCH_* vars в setup_env
2. `research-orchestrator` будет исполнять реальный конвейер

Иначе research-агенты доступны, но их детерминированный runner не запустится (честный WARN).

## Known gaps (verified on current machine)

| Артефакт | Live | Примечание |
|---|---|---|
| Plugin registered | ✅ | `opencode.jsonc` |
| Agents (15) | ✅ | `~/.config/opencode/agent` |
| Shared process docs (6) | ✅ | `~/.config/opencode/shared` |
| Runtime scripts (12) | ✅ | `~/.config/opencode/scripts/**` |
| setenv scripts | ✅ | `scripts/setup_env.{ps1,sh}` |
| RESEARCH runner scripts | ❌ | нет `run_research.sh`, `numeric_comparator.py`, `judge_brief.py`, `synthesizer.py` на этой машине; research-контур не исполняем до их переноса |