# Установка

Как развернуть trust-boundary guard локально: требования, установка, настройка ключей, проверка работоспособности, типичные проблемы.

---

## Требования

| Компонент | Версия | Обязательно | Назначение |
|-----------|--------|-------------|------------|
| Python | 3.10+ | да | stdlib: sqlite3, json, re, unicodedata, urllib |
| polza API key | — | для P2 cloud | primary классификатор gemma-4-26b (0.001₽/call) |
| ollama | любой | опционально | local fallback qwen2.5:0.5b (бесплатно, CPU) |

Зависимостей от pip нет. Guard использует только стандартную библиотеку Python. P0 (`session_guard.py`) работает вообще без внешних сервисов — только SQLite-чтение.

### Аппаратные ограничения

Local-классификатор `qwen2.5:0.5b` занимает 397 MB и работает на CPU. Модель `qwen2.5:1.5b` (986 MB) на 2 ГБ RAM получает OOM — поэтому fallback-цепочка на слабом железе заканчивается на 0.5b. Для лучшей локальной модели нужно ≥4 ГБ RAM.

---

## Установка

### 1. Скопировать `src/`

Два модуля должны лежать рядом (`semantic_layer.py` импортирует `session_guard.py`):

```
src/
├── session_guard.py     # P0
└── semantic_layer.py    # P2 (from session_guard import ...)
```

### 2. Создать конфиг из example

```bash
cp configs/guard_config.json.example configs/guard_config.json
chmod 600 configs/guard_config.json
```

`chmod 600` обязателен — конфиг содержит секретные API-ключи, owner-only. `load_config()` принудительно выставляет 0o600 при каждом запуске, но ручная установка прав после редактирования — правильная практика.

Файл `guard_config.json` уже в `.gitignore`:

```
guard_config.json
*.db
__pycache__/
```

### 3. Настроить ключи

Два способа, env имеет приоритет:

**Способ A — через переменную окружения (рекомендуется для CI):**

```bash
export POLZA_API_KEY="ваш-ключ-от-polza"
python3 src/semantic_layer.py ~/.local/share/opencode/opencode.db --json
```

`semantic_layer.py` читает `os.environ.get("POLZA_API_KEY")` и использует его **поверх** ключа из конфига.

**Способ B — в `guard_config.json`:**

```json
{
  "providers": {
    "cloud": {
      "model": "google/gemma-4-26b-a4b-it",
      "base_url": "https://polza.ai/api/v1/chat/completions",
      "api_key": "ваш-ключ-от-polza",
      "max_tokens": 20,
      "cost_per_call_rub": 0.001
    },
    "fallback": {
      "model": "sao10k/l3-lunaris-8b",
      "base_url": "https://polza.ai/api/v1/chat/completions",
      "api_key": "ваш-ключ-от-polza",
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

Полная схема конфига — [API.md](API.md), секция "guard_config.json schema".

### 4. (Опционально) Установить ollama для local fallback

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b      # 397 MB
ollama serve                  # 127.0.0.1:11434
```

Без ollama guard всё ещё работает — просто fallback-цепочка заканчивается на ALARM раньше. Если cloud недоступен и local не отвечает, guard выдаёт `alarm.level: CRITICAL` ("OPEN TO ATTACKS") и остаётся на P0-сигнатурах.

---

## Проверка установки

### Шаг 1. `--list-models` — конфиг загружен, провайдеры видны

```bash
python3 src/semantic_layer.py --list-models
```

Ожидаемый вывод — три провайдера (cloud, local, fallback) с моделью/URL/ценой и строка `budget: max=5.0 warn=4.0 alarm=4.8`. Если вместо этого `ERROR: config file not found` — не создан `guard_config.json` или указан неверный `--config`.

### Шаг 2. Синтетическая атака — P0 ловит инъекцию

```bash
python3 src/semantic_layer.py tests/synth.db --json
```

Ожидаемо: exit `1`, `"verdict": "FAIL"`, `"stats": {"p0_high": 4, ...}`. Это значит, что P0-сигнатуры нашли 4 high-suspicion вхождения в синтетической БД с известными инъекциями. Если exit `0` и `PASS` — guard сломан или БД пустая.

### Шаг 3. Формальные тесты P0

```bash
python3 tests/test_session_guard.py
```

7 кейсов: синтетические инъекции, фильтр по session, пустая БД, несуществующий файл (graceful, без traceback), валидность JSON. Ожидаемо: `RESULT: 7 passed, 0 failed`.

> Примечание: `test_session_guard.py` содержит захардкоженные пути `/tmp/factory-bubble/deep-bubble/...` — перед запуском обновите `GUARD` и `SYNTH` на актуальные пути (`src/session_guard.py` и `tests/synth.db`).

### Шаг 4. Реальная БД — бюджет и cloud работают

```bash
export POLZA_API_KEY="ваш-ключ"
python3 src/semantic_layer.py ~/.local/share/opencode/opencode.db --json --limit 10
```

Ожидаемо: `budget.spent` > 0, `provider: cloud`, `model: google/gemma-4-26b-a4b-it`. Если `alarm.level: CRITICAL` — см. troubleshooting ниже.

---

## Troubleshooting

### `ERROR: config file not found`

Конфиг не найден по пути. Default — `guard_config.json` рядом со `semantic_layer.py`. Проверьте:

```bash
ls -la configs/guard_config.json
python3 src/semantic_layer.py --list-models --config configs/guard_config.json
```

### ollama не запущен → ALARM DEGRADED

Если `polza` доступен, но `ollama` нет — primary cloud работает, fallback на local не сработает при timeout cloud. Guard продолжит на cloud. ALARM DEGRADED появится, только когда **и** cloud, **и** local одновременно недоступны.

Проверка ollama:

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool
```

Если соединение refused — `ollama serve` не запущен. Запуск в фоне:

```bash
setsid ollama serve >/dev/null 2>&1 &
```

### polza баланс исчерпан → budget exhausted → CRITICAL

Если `budget.exhausted: true` и `alarm.level: CRITICAL` — бюджет потрачен, cloud заблокирован preventive-stop, local тоже не ответил.

```
budget: spent=5.000000 max=5.000000 remaining=0.000000 exhausted=true
alarm: level=CRITICAL GUARD CRITICAL — OPEN TO ATTACKS (no classifier available)
```

Решения:
- Пополнить баланс polza.
- Поднять `--budget` на разовый прогон: `--budget 20.0`.
- Изменить `budget.max_cost_rub` в конфиге.
- Убедиться, что ollama отвечает (тогда будет DEGRADED, не CRITICAL — local продолжит работать).

### Preventive STOP при мизерном бюджете

`ClassifierChain._cloud_usable()` проверяет `budget.remaining >= cost_per_call * P2_VOTES` **до** вызова. При `--budget 0.0001` и `cost_per_call=0.001` × 3 votes = 0.003 — даже первый вызов блокируется, `spent` остаётся 0.0, сразу ALARM. Это intentional — не даём стартовать прогон, который точно не завершит majority-vote.

### `Traceback` в stderr

Guard спроектирован на graceful-обработку: `OpenDBError` (БД не открылась) и `ConfigError` (конфиг битый) дают короткое `ERROR: ...` без traceback. Если traceback появился — это баг, сообщите с приложением команды и версии.

### False positives на легитимных docs

P2 на реальной БД может помечать benign webfetch-документацию (opencode.ai/docs, GitHub raw) как YES, потому что в тексте встречаются слова "ignore previous" в техническом контексте. Discussion-маркеры в P0 (окно ±80 для STRONG_EN) смягчают это, но P2-классификатор таких маркеров не имеет. Mitigation — allowlist benign источников (planned, не реализовано). Сейчас: проверяйте `excerpt` в findings вручную.

---

## Что дальше

- [ARCHITECTURE.md](ARCHITECTURE.md) — как устроены слои и почему так.
- [API.md](API.md) — полный справочник аргументов и JSON-схемы.
- [ADVERSARIAL.md](ADVERSARIAL.md) — как прогнать 18 техник обхода и проверить bypass-rate.