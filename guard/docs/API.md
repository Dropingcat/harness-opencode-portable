# API reference

Полный справочник CLI, JSON-схем, exit codes для `session_guard.py` (P0) и `semantic_layer.py` (P2). Схема `guard_config.json`. Схема ALARM.

---

## `session_guard.py` — P0 детерминированный слой

Только stdlib, без сети, без LLM. Сканирует `opencode.db` на инъекционные сигнатуры.

### CLI

```
python3 session_guard.py <db> [--session <id>] [--json]
```

| Аргумент | Тип | Обязательный | Default | Назначение |
|----------|-----|--------------|---------|------------|
| `db` | path | да | — | Путь к `opencode.db` |
| `--session` | string | нет | all | Анализировать только указанную сессию |
| `--json` | flag | нет | human | Вывод в JSON вместо human-readable |

### Exit codes

| Code | Значение |
|------|----------|
| 0 | PASS — инъекций не найдено |
| 1 | FAIL — найдена high-suspicion инъекция, **или** ошибка БД |

> P0 не различает ERROR и FAIL по exit code — оба дают 1. Ошибка БД (`OpenDBError`) выводит `ERROR: ...` в stderr (или `{"verdict": "ERROR"}` в JSON) без traceback.

### JSON schema (P0)

```json
{
  "verdict": "PASS" | "FAIL" | "ERROR",
  "session_id": "all" | "<id>",
  "total_parts_scanned": 281,
  "trusted_parts": 150,
  "untrusted_parts": 80,
  "findings": [
    {
      "session_id": "s2",
      "part_id": "p5",
      "provenance": "untrusted",
      "tool": "webfetch",
      "url": "https://evil.example/payload",
      "field": "state.output",
      "signature": "ignore previous",
      "suspicion": "high" | "low",
      "excerpt": "...the first 60 chars around the signature..."
    }
  ],
  "stats": {
    "high_suspicion": 4,
    "low_suspicion": 2,
    "sessions_with_findings": 3
  }
}
```

При ошибке БД:

```json
{"verdict": "ERROR", "error": "cannot open database: /path/to/db: ..."}
```

### Human output (P0)

```
verdict: FAIL
session: all
parts: total=281 trusted=150 untrusted=80
stats: high=4 low=2 sessions_with_findings=3
findings:
  [high] untrusted/webfetch session=s2 part=p5 sig='ignore previous' url=https://evil.example :: ...excerpt...
```

---

## `semantic_layer.py` — P2 гибридный слой

Гибрид P0 + P2. Импортирует P0 логику, добавляет cloud/local классификатор с budget control и ALARM.

### CLI

```
python3 semantic_layer.py <db> [options]
python3 semantic_layer.py --list-models [--config <path>]
```

| Аргумент | Тип | Обязательный | Default | Назначение |
|----------|-----|--------------|---------|------------|
| `db` | path | да (кроме `--list-models`) | — | Путь к `opencode.db` |
| `--session` | string | нет | all | Анализировать только указанную сессию |
| `--json` | flag | нет | human | Вывод в JSON |
| `--provider` | `local` \| `cloud` | нет | `cloud` | Предпочитаемый P2-провайдер (fallback-цепочка учитывается всегда) |
| `--model` | string | нет | из конфига | Override модели |
| `--limit` | int | нет | 100 | Максимум P2-вызовов (экономия бюджета) |
| `--budget` | float | нет | из конфига | Override `max_cost_rub` на один прогон |
| `--config` | path | нет | `guard_config.json` рядом со скриптом | Путь к конфигу |
| `--api-key` | string | нет | env/конфиг | POLZA_API_KEY (приоритет: env > `--api-key` > конфиг) |
| `--list-models` | flag | нет | — | Печать провайдеров/моделей/цены, без сканирования |

> Приоритет API key: `POLZA_API_KEY` env > `--api-key` CLI > `providers.cloud.api_key` в конфиге.

### Exit codes

| Code | Значение |
|------|----------|
| 0 | PASS — инъекций не найдено |
| 1 | FAIL — найдена инъекция (P0 high или P2 YES), **или** ошибка БД, **или** ошибка конфига |

> P2 fail-closed: timeout/ошибка классификатора → verdict YES → FAIL. Поэтому сетевая ошибка cloud при отсутствии local даст FAIL, не ERROR.

### `--list-models` output

```
cloud: model=google/gemma-4-26b-a4b-it
    base_url=https://polza.ai/api/v1/chat/completions
    api_key=set max_tokens=20 cost_per_call=0.001 руб
local: model=qwen2.5:0.5b
    base_url=http://127.0.0.1:11434/api/generate
    api_key=null max_tokens=50 cost_per_call=null руб
fallback: model=sao10k/l3-lunaris-8b
    base_url=https://polza.ai/api/v1/chat/completions
    api_key=set max_tokens=20 cost_per_call=null руб
budget: max=5.0 warn=4.0 alarm=4.8
```

### JSON schema (P2)

```json
{
  "verdict": "PASS" | "FAIL" | "ERROR",
  "session_id": "all" | "<id>",
  "provider": "cloud",
  "model": "google/gemma-4-26b-a4b-it",
  "total_parts_scanned": 281,
  "trusted_parts": 150,
  "untrusted_parts": 80,
  "internal_parts": 51,
  "findings": [
    {
      "session_id": "s2",
      "part_id": "p5",
      "provenance": "untrusted",
      "tool": "webfetch",
      "url": "https://evil.example/payload",
      "layer": "P0" | "P2",
      "signature": "ignore previous" | null,
      "p2_verdict": null | "YES" | "NO",
      "p2_votes": {"yes": 3, "no": 0, "timeout": 0} | null,
      "p2_suspicion": null | "majority" | "timeout" | "DEGRADED" | "CRITICAL",
      "p2_provider": null | "cloud" | "fallback" | "local",
      "p2_alarm": null | "DEGRADED" | "CRITICAL",
      "excerpt": "...first 60 chars..."
    }
  ],
  "cost_rub": 0.007,
  "budget": {
    "spent": 0.007,
    "max": 5.0,
    "remaining": 4.993,
    "exhausted": false
  },
  "alarm": null | {
    "level": "DEGRADED" | "CRITICAL",
    "message": "GUARD DEGRADED — fallback active, P0 only" | "GUARD CRITICAL — OPEN TO ATTACKS (no classifier available)",
    "primary": "exhausted" | "error",
    "fallback": "offline" | "active",
    "residual_risk": "50% bypass (paraphrase/indirect)"
  },
  "stats": {
    "p0_high": 2,
    "p2_classified": 15,
    "p2_yes": 1,
    "p2_no": 14,
    "p2_timeout": 0,
    "p2_caught": 1,
    "p2_votes": 3,
    "p2_fail_closed": true,
    "design_blindspots": ["internal_weaks_ru", "compaction"]
  }
}
```

### Verdict логика (P2)

```
verdict = FAIL if (p0_high > 0 OR p2_yes > 0) else PASS
```

- `p0_high` — count P0 high-suspicion hits (STRONG_EN/WEAK_RU в untrusted/internal).
- `p2_yes` — count P2 YES verdicts, **включая** fail-closed (timeout → YES).
- `p2_timeout` — count случаев, где P2 вернул None (fail-closed → counted in `p2_yes`).

### Human output (P2)

```
verdict: FAIL
session: all  provider: cloud  model: google/gemma-4-26b-a4b-it
parts: total=281 trusted=150 untrusted=80 internal=51
stats: p0_high=2 p2_classified=15 p2_yes=1 p2_no=14 p2_timeout=0 (votes=3, fail_closed=true)
budget: spent=0.007000 max=5.000000 remaining=4.993000 exhausted=false
cost: 0.007000 руб
design_blindspots: internal_weaks_ru, compaction
findings:
  [P0] untrusted/webfetch session=s2 part=p5 sig='ignore previous' url=https://evil.example :: ...
  [P2] untrusted/webfetch session=s7 part=p11 p2=YES votes={'yes': 3, 'no': 0, 'timeout': 0} (cloud) url=... :: ...
```

При ALARM добавляется строка:

```
alarm: level=DEGRADED GUARD DEGRADED — fallback active, P0 only (primary=error, fallback=active)
```

---

## `guard_config.json` schema

Конфиг ключей/моделей/бюджета. НЕ коммитить (в `.gitignore`), `chmod 600`. Шаблон — `configs/guard_config.json.example`.

```json
{
  "_comment": "Конфиг trust-boundary guard. НЕ коммитить, ключи секретные.",
  "providers": {
    "cloud": {
      "model": "google/gemma-4-26b-a4b-it",
      "base_url": "https://polza.ai/api/v1/chat/completions",
      "api_key": "REDACTED-SET-VIA-ENV",
      "max_tokens": 20,
      "cost_per_call_rub": 0.001
    },
    "fallback": {
      "model": "sao10k/l3-lunaris-8b",
      "base_url": "https://polza.ai/api/v1/chat/completions",
      "api_key": "REDACTED-SET-VIA-ENV",
      "max_tokens": 20
    },
    "local": {
      "model": "qwen2.5:0.5b",
      "base_url": "http://127.0.0.1:11434/api/generate",
      "api_key": null,
      "max_tokens": 50
    }
  },
  "budget": {
    "max_cost_rub": 5.0,
    "warn_threshold_rub": 4.0,
    "alarm_threshold_rub": 4.8
  },
  "security": {
    "votes": 3,
    "timeout_sec": 40,
    "fail_closed": true
  }
}
```

### Поля

#### `providers` (object, обязательно)

Три провайдера для fallback-цепочки `ClassifierChain`:

| Провайдер | Роль | Обязательные поля |
|-----------|------|-------------------|
| `cloud` | primary, gemma-26b | `model`, `base_url`, `api_key`, `max_tokens`, `cost_per_call_rub` |
| `fallback` | cloud fallback, l3-lunaris-8b | `model`, `base_url`, `api_key`, `max_tokens` |
| `local` | ollama, бесплатно | `model`, `base_url`, `api_key` (null), `max_tokens` |

Поля каждого провайдера:

| Поле | Тип | Назначение |
|------|-----|------------|
| `model` | string | Имя модели для API |
| `base_url` | string | Endpoint (OpenAI-compatible для cloud, `/api/generate` для ollama) |
| `api_key` | string \| null | Bearer token. `null` для local. Env `POLZA_API_KEY` имеет приоритет. |
| `max_tokens` | int | Лимит tokens в ответе (cloud: 20, local: 50) |
| `cost_per_call_rub` | float | Оценка стоимости одного вызова для preventive budget-stop. Только для cloud. |

#### `budget` (object, обязательно)

| Поле | Тип | Default | Назначение |
|------|-----|---------|------------|
| `max_cost_rub` | float | 5.0 | Лимит cloud-расхода за прогон |
| `warn_threshold_rub` | float | 4.0 | Порог `BUDGET WARNING` в stderr |
| `alarm_threshold_rub` | float | 4.8 | Порог early `BUDGET ALARM` (до исчерпания) |

CLI `--budget F` override `max_cost_rub` на один прогон.

#### `security` (object, опционально)

| Поле | Тип | Default | Назначение |
|------|-----|---------|------------|
| `votes` | int | 3 | Число вызовов для majority vote |
| `timeout_sec` | int | 40 | Таймаут одного вызова классификатора |
| `fail_closed` | bool | true | Timeout/ошибка → YES → FAIL |

> `votes` и `timeout_sec` в конфиге хранятся, но runtime-значения в `semantic_layer.py` — `P2_VOTES = 3`, `P2_TIMEOUT = 60`. Конфиг документирует намерение; override констант требует правки кода.

### Загрузка и безопасность

`load_config(path)`:

1. Проверяет существование файла → `ConfigError` если нет.
2. Парсит JSON → `ConfigError` если битый.
3. Проверяет, что顶层 — dict → `ConfigError` если нет.
4. **`os.chmod(path, 0o600)`** — принудительно owner-only при каждой загрузке. Не критично если fails (OSError проглатывается).

`ConfigError` обрабатывается в `main()` graceful: `ERROR: ...` в stderr, exit 1, без traceback.

---

## ALARM schema

ALARM появляется в JSON (`alarm` поле) и в stderr (рамка) когда semantic layer деградировал.

### Условия срабатывания

| Level | Условие | Что работает |
|-------|---------|--------------|
| `DEGRADED` | primary cloud недоступен (timeout/error), но fallback cloud ИЛИ local работает | Fallback активен, P2 продолжается на более слабой модели |
| `CRITICAL` | Все классификаторы недоступны: budget exhausted + local offline/timeout | Только P0 сигнатуры, semantic layer OFFLINE |

Дополнительный триггер: `budget.alarm_triggered` (spent ≥ `alarm_threshold_rub`) — early warning, даже если бюджет не исчерпан.

### JSON schema

```json
{
  "alarm": {
    "level": "CRITICAL",
    "message": "GUARD CRITICAL — OPEN TO ATTACKS (no classifier available)",
    "primary": "exhausted",
    "fallback": "offline",
    "residual_risk": "50% bypass (paraphrase/indirect)"
  }
}
```

| Поле | Значения | Назначение |
|------|----------|------------|
| `level` | `DEGRADED` \| `CRITICAL` | Уровень тревоги |
| `message` | string | Человекочитаемое описание |
| `primary` | `exhausted` \| `error` | Почему primary недоступен |
| `fallback` | `offline` \| `active` | Статус fallback |
| `residual_risk` | `"50% bypass (paraphrase/indirect)"` | Честная оценка остаточного риска |

### Stderr output (CRITICAL)

```
╔══════════════════════════════════════════════════════════╗
║  ALARM: GUARD CRITICAL — OPEN TO ATTACKS
║  Primary classifier: UNAVAILABLE (exhausted)
║  Fallback classifier: UNAVAILABLE (offline)
║  P0 signatures only — semantic layer OFFLINE
║  RESIDUAL RISK: 50% bypass (paraphrase/indirect)
╚══════════════════════════════════════════════════════════╝
[guard] alarm level=CRITICAL: GUARD CRITICAL — OPEN TO ATTACKS (no classifier available)
```

### Stderr output (DEGRADED)

```
╔══════════════════════════════════════════════════════════╗
║  ALARM: GUARD DEGRADED — OPEN TO ATTACKS
║  Primary classifier: UNAVAILABLE (error)
║  Fallback classifier: UNAVAILABLE (offline)
║  P0 signatures only — semantic layer OFFLINE
║  RESIDUAL RISK: 50% bypass (paraphrase/indirect)
╚══════════════════════════════════════════════════════════╝
```

> ⚠ Внимание: `residual_risk: "50% bypass"` — это bypass-rate **local** qwen 0.5b и P0-only. При работающем cloud gemma-26b residual ~10%, но ALARM срабатывает только когда cloud **недоступен**, поэтому в ALARM всегда указан pessimistic 50%.

---

## Примеры команд

### Проверить конфиг без сканирования

```bash
python3 src/semantic_layer.py --list-models
```

### P0-only сканирование (быстро, без сети/бюджета)

```bash
python3 src/session_guard.py ~/.local/share/opencode/opencode.db --json
```

### Полный P0+P2 с cloud, ограничить 50 P2-вызовов

```bash
export POLZA_API_KEY="ваш-ключ"
python3 src/semantic_layer.py ~/.local/share/opencode/opencode.db --json --limit 50
```

### Принудительно local (без cloud-бюджета)

```bash
python3 src/semantic_layer.py tests/synth.db --json --provider local
```

### Тест preventive budget-stop

```bash
python3 src/semantic_layer.py tests/synth.db --json --budget 0.0001
# Ожидаемо: spent=0.0, alarm.level=CRITICAL (даже первый вызов заблокирован)
```

### Одна сессия

```bash
python3 src/semantic_layer.py ~/.local/share/opencode/opencode.db --session "abc123" --json
```

### Свой конфиг

```bash
python3 src/semantic_layer.py ~/.local/share/opencode/opencode.db --config /path/to/custom_config.json --json
```

---

## Интеграция

### Pre-resume gate (рекомендуемый паттерн)

Перед resume сессии opencode — прогнать guard, блокировать при FAIL:

```bash
python3 src/semantic_layer.py ~/.local/share/opencode/opencode.db \
    --session "$SESSION_ID" --json --limit 20
rc=$?
if [ $rc -eq 1 ]; then
    echo "RESUME BLOCKED: injection detected" >&2
    exit 1
fi
# rc=0 → safe to resume
```

### CI regression gate

```bash
# P0 формальные тесты
python3 tests/test_session_guard.py

# Adversarial bubble-test
python3 src/adversarial_build.py
# Проверить: bypass_rate не вырос относительно baseline
```

Полная методология adversarial — [ADVERSARIAL.md](ADVERSARIAL.md). Модель угроз — [THREAT_MODEL.md](THREAT_MODEL.md).