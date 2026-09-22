# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: WP-4 «Инфраструктура и Безопасность»
**Проект:** Agent-Kirpichik  
**Версия спецификации:** 0.2  
**Зависимости:** 🔴 WP-0 (Контракты, `SandboxRunner`, `LLMProvider`)  
**Связанные документы:** `THREAT_MODEL.md`, `CONFIG_GUIDE.md`, `RUNBOOK.md`
**Приоритет:** 🔴 Critical (Безопасность)  
**Ожидаемое время выполнения:** 4–5 дней  

## 1. Цели и границы ответственности
**Цель:** Реализовать безопасную среду исполнения кода, адаптеры верификации и шлюз для LLM с контролем ресурсов и бюджета.  
**Границы:**
*   ✅ **Входит:** Local/Docker Sandbox, Verifier Adapter, LLM Gateway (cache/budget/routing), Threat Model.
*   ❌ **Не входит:** Бизнес-логика агентов, оркестрация, генерация промтов.

> ⚠️ **Железное правило безопасности:** Песочница считается враждебной средой по умолчанию. Любой код, переданный в `SandboxRunner`, потенциально вредоносен. Изоляция — не опция, а обязательное требование.

---

## 2. Артефакты и структура файлов

```text
src/infra/
├── __init__.py
├── sandbox/
│   ├── __init__.py
│   ├── protocol.py         # Дублирование SandboxRunner из WP-0 для удобства
│   ├── local_sandbox.py    # Реализация через subprocess + resource limits
│   ├── docker_sandbox.py   # Реализация через docker SDK
│   └── cleanup.py          # Гарантированная очистка ресурсов
├── verifier/
│   ├── __init__.py
│   ├── adapter.py          # Запуск инструментов внутри sandbox
│   └── parsers/            # Парсеры вывода flake8/mypy/pytest
│       ├── flake8_parser.py
│       ├── mypy_parser.py
│       └── pytest_parser.py
└── llm/
    ├── __init__.py
    ├── gateway.py          # Кэширование, бюджет, роутинг, fallback
    ├── cache.py            # SQLite/Redis backend
    └── budget_tracker.py   # Учет токенов и стоимости

tests/unit/test_wp4/
├── test_local_sandbox.py
├── test_docker_sandbox.py
├── test_verifier_adapter.py
├── test_llm_gateway.py
└── security/               # Тесты на проникновение
    ├── test_escape_attempts.py
    ├── test_resource_exhaustion.py
    └── fixtures/           # Вредоносные скрипты
        ├── fork_bomb.py
        ├── disk_filler.py
        └── network_access.py

docs/
└── THREAT_MODEL.md         # Модель угроз для песочницы
```

---

## 3. Детальные требования к компонентам

### 3.1. Local Sandbox (`local_sandbox.py`)
Базовая реализация для разработки и тестирования.

**Требования:**
1.  Реализует `SandboxRunner` из WP-0.
2.  **Изоляция:**
    *   Временная директория создается через `tempfile.mkdtemp()`.
    *   Права на директорию: `0o700` (только владелец).
    *   Удаление гарантировано через контекстный менеджер (`with LocalSandbox() as sb:`).
3.  **Ограничение ресурсов (Linux):**
    *   CPU time: `resource.setrlimit(RLIMIT_CPU, ...)`
    *   Memory: `resource.setrlimit(RLIMIT_AS, ...)`
    *   File size: `resource.setrlimit(RLIMIT_FSIZE, ...)`
    *   Forks: `resource.setrlimit(RLIMIT_NPROC, 1)` (запрет fork bomb)
4.  **Ограничение ресурсов (Windows):**
    *   Job Objects API для ограничения CPU/Memory.
    *   Если Job Objects недоступны — явный warning в логах + таймаут как единственная защита.
5.  **Таймауты:** Вложенные. Общий > инструментальный > системный.
6.  **Сеть:** Запрещена по умолчанию. На Linux через `unshare --net` или firewall rules. На Windows — документированное ограничение (best effort).

**⚠️ Контроль ошибок:**
*   При ошибке создания ограничений — **FAIL CLOSED**. Не запускать код без ограничений.
*   При ошибке очистки — логировать CRITICAL + пытаться удалить при следующем запуске.
*   Никогда не передавать путь к tmpdir в аргументах командной строки (race condition). Использовать env vars или cwd.

### 3.2. Docker Sandbox (`docker_sandbox.py`)
Production-ready реализация.

**Требования:**
1.  Реализует `SandboxRunner`.
2.  **Контейнер:**
    *   Образ: минимальный Python (slim/alpine).
    *   `network_mode="none"` (полная изоляция сети).
    *   `read_only=True` (filesystem read-only, кроме /tmp).
    *   `mem_limit`, `cpus`, `pids_limit` заданы явно.
    *   `security_opt=["no-new-privileges:true"]`.
3.  **Жизненный цикл:**
    *   Контейнер создается на каждый вызов `execute()` ИЛИ переиспользуется с полной очисткой `/tmp` между вызовами (конфигурируемо).
    *   Гарантированное удаление контейнера даже при crash процесса хоста (через `auto_remove=True` или cleanup hook).
4.  **Передача файлов:** Через volume mount (read-only для input, read-write для /tmp/output). Никаких `docker cp` для больших файлов.
5.  **Таймаут:** `container.stop(timeout=...)` + `container.kill()` как fallback.

**⚠️ Контроль ошибок:**
*   Проверка доступности Docker daemon при инициализации.
*   Обработка `ContainerError`, `ImageNotFound`, `APIError`.
*   Логирование ID контейнера для каждого вызова (для forensics).

### 3.3. Verifier Adapter (`verifier/adapter.py`)
Запуск инструментов верификации ВНУТРИ песочницы.

**Требования:**
1.  Метод `verify(artifact: Artifact, tools: List[str], sandbox: SandboxRunner) -> ToolResults`.
2.  Для каждого инструмента:
    *   Генерирует скрипт-обертку, который запускает инструмент и выводит результат в JSON.
    *   Передает скрипт и файлы артефакта в sandbox.
    *   Парсит stdout через соответствующий parser.
3.  **Обработка ошибок парсинга:**
    *   Если вывод невалиден → возвращать `{"error": "parse_failed", "raw_output": "..."}`.
    *   НИКОГДА не бросать исключение при невалидном выводе инструмента.
4.  **Безопасность:** Скрипты-обертки генерируются из шаблонов, НЕ из пользовательского ввода. Файлы артефакта передаются как данные, не как код.

### 3.4. LLM Gateway (`llm/gateway.py`)
Единая точка входа для всех LLM-вызовов.

**Требования:**
1.  Реализует `LLMProvider` из WP-0.
2.  **Кэширование:**
    *   Ключ: SHA256 от нормализованных сообщений + модель + температура.
    *   Backend: SQLite (default) / Redis (config).
    *   TTL: конфигурируемый.
    *   Cache hit логируется отдельно.
3.  **Бюджетирование:**
    *   Трекинг токенов и стоимости (USD) per task и global.
    *   При превышении `max_tokens_per_task` → возвращать ошибку, НЕ делать вызов.
    *   При достижении `alert_threshold` → логировать WARNING.
    *   Стоимость берется из конфига (цены моделей), не из API ответа (для предсказуемости).
4.  **Роутинг:**
    *   Поддержка нескольких моделей (coder_model, critic_model, auditor_model).
    *   Fallback chain: primary → secondary → error.
5.  **Retry Logic:**
    *   Retry только на 429, 500, 502, 503, timeout.
    *   Exponential backoff + jitter.
    *   Max retries configurable.
    *   На 400/401/403 — немедленная ошибка без retry.

**⚠️ Контроль ошибок:**
*   API ключи ТОЛЬКО через env vars / secret manager. Никогда в коде или логах.
*   Логируют запросы БЕЗ содержимого prompt (или с redaction).
*   При ошибке бюджета — четкое сообщение с указанием лимита и текущего расхода.

---

## 4. Критерии приемки (Definition of Done)

### 4.1. Безопасность
- [ ] Local Sandbox проходит все тесты из `tests/security/`.
- [ ] Docker Sandbox имеет `network_mode="none"` и `read_only=True`.
- [ ] Fork bomb, disk filler, network access блокируются в обеих реализациях.
- [ ] API ключи не присутствуют в коде, логах, git history.
- [ ] Threat Model документирована и подписана.

### 4.2. Функциональные
- [ ] Verifier корректно парсит вывод flake8/mypy/pytest.
- [ ] Verifier возвращает структурированную ошибку при невалидном выводе.
- [ ] LLM Gateway кэширует идентичные запросы.
- [ ] LLM Gateway блокирует вызовы при превышении бюджета.
- [ ] LLM Gateway делает retry на transient errors.
- [ ] Cleanup гарантирует удаление ресурсов при любых условиях.

### 4.3. Тестовые
- [ ] Security tests: ≥ 10 сценариев проникновения/исчерпания ресурсов.
- [ ] Unit tests: покрытие ≥ 90% для parsers и gateway.
- [ ] Integration test: полный цикл verify с real sandbox.
- [ ] Chaos test: убийство процесса во время execute() → ресурсы очищены.

### 4.4. Структурные
- [ ] Нет хардкода путей, таймаутов, лимитов.
- [ ] Все конфиги загружаются из `config.yaml` + env override.
- [ ] Type hints полные, mypy strict passes.
- [ ] Docstrings включают security considerations.

---

## 5. Риски и митигации

| Риск | Вероятность | Влияние | Митигация |
| :--- | :--- | :--- | :--- |
| Побег из Local Sandbox | Средняя | Критическое | Threat model. Docker для production. Local только для dev. Документированные ограничения. |
| Утечка API ключей | Низкая | Критическое | Secret scanning в CI. Env vars only. Redaction в логах. |
| Resource exhaustion хоста | Средняя | Высокое | Жесткие RLIMIT/Job Objects. Docker limits. Monitoring. |
| LLM budget overrun | Высокая | Среднее | Pre-check бюджета. Alert threshold. Hard limit per task. |
| Parser ломается на новом формате | Средняя | Среднее | Defensive parsing. Raw output preservation. Version pinning инструментов. |
| Docker daemon недоступен | Низкая | Высокое | Graceful degradation to Local Sandbox + warning. Health check при старте. |

---

## 6. Порядок выполнения

1.  Написать `THREAT_MODEL.md` (до кода!).
2.  Реализовать `local_sandbox.py` + security tests.
3.  Реализовать `verifier/parsers/` + unit tests.
4.  Реализовать `verifier/adapter.py` + integration test с local sandbox.
5.  Реализовать `llm/cache.py` + `budget_tracker.py` + unit tests.
6.  Реализовать `llm/gateway.py` + integration tests.
7.  Реализовать `docker_sandbox.py` + security tests.
8.  Прогнать полный security + unit + integration suite.
9.  Code review с фокусом на безопасность.
10. Открыть PR.

---

## 7. Связь с другими WP

| WP | Зависимость от WP-4 | Что передает WP-4 |
| :--- | :--- | :--- |
| WP-1 | Оркестратор использует SandboxRunner и Verifier | Интерфейсы + реализации |
| WP-2 | Критик получает tool_results от Verifier | Структура ToolResults |
| WP-3 | Аудитор анализирует tool_usage_consistency | Метаданные верификации |
| Future | Production deployment | Docker sandbox + LLM gateway |

---

## 8. Чек-лист для ревьюера (SECURITY FOCUS)

- [ ] **NO NETWORK:** В sandbox нет доступа к сети (проверено тестами).
- [ ] **RESOURCE LIMITS:** CPU/RAM/PIDs ограничены в обеих реализациях.
- [ ] **CLEANUP GUARANTEED:** Контекстный менеджер / auto_remove / finally block.
- [ ] **NO SECRETS IN CODE:** grep по репозиторию на предмет ключей/токенов.
- [ ] **FAIL CLOSED:** При ошибке изоляции код НЕ выполняется.
- [ ] **PARSER SAFETY:** Парсеры не исполняют код, не используют eval/exec.
- [ ] **BUDGET CHECK:** Бюджет проверяется ДО вызова API.
- [ ] **LOG REDACTION:** Промты и ответы не логируются в plaintext.
- [ ] **THREAT MODEL EXISTS:** Документ создан и отражает текущую реализацию.

---

**Финальное напоминание:**  
WP-4 — это не просто «инфраструктура». Это **граница доверия** системы. Ошибки в WP-1/WP-2/WP-3 приводят к неправильным результатам. Ошибки в WP-4 приводят к **компрометации**. Относитесь к этому блоку с соответствующей строгостью.
