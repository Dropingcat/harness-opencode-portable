Принято. Ниже представлено детальное техническое задание для блока **WP-1: Ядро Оркестрации и State Machine**.

Этот документ является прямым продолжением WP-0. Он написан с учетом того, что все модели (`models.py`) и интерфейсы (`protocols.py`) уже существуют и неизменны. Задача разработчика WP-1 — реализовать **детерминированную логику управления**, не зависящую от LLM.

---

# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: WP-1 «Ядро Оркестрации и State Machine»
**Проект:** Agent-Kirpichik  
**Версия спецификации:** 0.2  
**Зависимости:** 🔴 WP-0 (Контракты) — **ОБЯЗАТЕЛЬНО ЗАВЕРШЕН**  
**Приоритет:** 🔴 Critical  
**Ожидаемое время выполнения:** 3–4 дня  

## 1. Цели и границы ответственности
**Цель:** Реализовать «мозг» системы — детерминированный цикл управления задачей, машину состояний и вычисление метрик прогресса.  
**Границы:**
*   ✅ **Входит:** State Machine, Orchestrator Loop, ProcessMetricsEvaluator, PolicyEngine (Sync), Trace Management.
*   ❌ **Не входит:** Генерация кода/текста (LLM), вызов внешних инструментов (Sandbox), анализ *содержания* артефактов (Critic/Auditor).

> ⚠️ **Критическое ограничение:** В этом блоке **ЗАПРЕЩЕНЫ** любые вызовы LLM API. Вся логика должна быть воспроизводимой, тестируемой и быстрой (<1ms на итерацию без учета I/O).

---

## 2. Артефакты и структура файлов

```text
src/core/
├── state_machine.py      # Канбан и правила переходов
├── orchestrator.py       # Главный цикл управления
├── metrics_evaluator.py  # Детерминированный расчет ProcessMetrics
└── policy_engine.py      # Синхронные анти-правила (Anti-Hack/Lazy)

tests/unit/test_wp1/
├── test_state_machine.py
├── test_orchestrator.py
├── test_metrics_evaluator.py
└── test_policy_engine.py
```

---

## 3. Детальные требования к компонентам

### 3.1. State Machine (`state_machine.py`)
Реализует жесткие правила переходов статусов задачи.

**Требования:**
1.  Использовать Enum `TaskStatus` из WP-0.
2.  Матрица переходов должна быть **явной константой** (dict of sets), а не скрытой в if/else.
3.  Метод `transition(current, target) -> TaskStatus`:
    *   Возвращает новый статус при успехе.
    *   Бросает `InvalidTransitionError(current, target)` при нарушении правил.
    *   **НЕ** меняет состояние объекта напрямую (чистая функция).
4.  Метод `can_mark_done(task_state) -> bool`:
    *   Проверяет наличие артефакта.
    *   Проверяет отсутствие `severity=BLOCKING` в последнем `CriticReport`.
    *   Проверяет `compliant=True` в последнем `AuditReport` (если аудит проводился).

**Матрица переходов (согласовано):**
| From | To | Условие |
| :--- | :--- | :--- |
| BACKLOG | IN_PROGRESS | Старт задачи |
| IN_PROGRESS | REVIEW | Verdict == PASS |
| IN_PROGRESS | BLOCKED | RequiresUser OR Limit OR AuditorBlock |
| REVIEW | DONE | FinalAudit OK OR UserConfirm |
| REVIEW | BLOCKED | FinalAudit FAIL |
| BLOCKED | IN_PROGRESS | UserResolved |
| BLOCKED | DONE | UserForceComplete (с флагом forced) |

### 3.2. Process Metrics Evaluator (`metrics_evaluator.py`)
Вычисляет `ProcessMetrics` из списка `TraceEntry`. **Никаких LLM.**

**Требования:**
1.  Чистая функция: `evaluate(trace: List[TraceEntry]) -> ProcessMetrics`.
2.  **Log Completeness:** `%` итераций, где есть `artifact_hash`, `critic_verdict`, `timestamp`.
3.  **Trace Integrity:** Проверка монотонности `iteration` и отсутствия дубликатов.
4.  **Semantic Diff Ratio:**
    *   Если есть доступ к предыдущему артефакту: `(len(non_whitespace_diff) / len(total_diff))`.
    *   Если нет: вернуть `None` или дефолтное значение.
    *   ⚠️ **Важно:** Не использовать difflib SequenceMatcher для больших файлов без лимитов. Ограничить размер сравниваемых файлов (например, 1MB).
5.  **Fix Repetition Rate:**
    *   Сравнивать хэши `findings` последних N итераций.
    *   Формула: `count(repeated_findings) / total_findings_last_3_iters`.
6.  **Iteration Time Variance:** Дисперсия длительности последних 5 итераций.
7.  **Tool Usage Consistency:** Булево поле. True если во всех итерациях, где был верификатор, он вернул результат (не таймаут/ошибка инфраструктуры).
8.  **Contract Violations Count:** Подсчет ошибок валидации схем (берется из логов оркестратора, передается как параметр или хранится в trace metadata).

**Валидация результата:**
*   Все float-метрики должны быть в диапазоне [0.0, 1.0].
*   При пустом trace возвращать нулевые/дефолтные значения, **не** бросать исключения.

### 3.3. Policy Engine (`policy_engine.py`)
Синхронные проверки **ДО** передачи данных критику или **ПОСЛЕ** получения вердикта.

**Требования:**
1.  Интерфейс: `check(iteration: int, artifact: Artifact, prev_artifact: Artifact | None, critic_report: CriticReport | None) -> PolicyCheckResult`.
2.  `PolicyCheckResult` содержит: `passed: bool`, `violations: List[str]`, `action: CONTINUE | RETRY | BLOCK`.
3.  **Anti-Hack (Test Modification):**
    *   Сравнить списки файлов `artifact.files` и `prev_artifact.files`.
    *   Если изменился файл, matching `test_*.py` или `*_test.py` → `BLOCK`.
    *   Исключение: если задача явно помечена как "update tests" в metadata.
4.  **Anti-Lazy (Cosmetic Changes):**
    *   Если `prev_artifact` существует:
    *   Посчитать diff. Если `len(stripped_diff) < MIN_MEANINGFUL_CHARS` (конфиг, default=10) → `RETRY` с флагом `force_substantive_change`.
5.  **Anti-Oscillation:**
    *   Если `critic_report` предоставлен:
    *   Проверить, повторяются ли одни и те же `blocking` findings > 2 раз подряд. → `BLOCK` (стагнация).
6.  Конфигурация порогов должна загружаться из `config.yaml`, а не хардкодиться.

### 3.4. Orchestrator (`orchestrator.py`)
Главный цикл. Собирает всё вместе.

**Требования:**
1.  Класс `Orchestrator`, принимающий зависимости через `__init__`:
    *   `coder: Callable[[str, dict, list], Artifact]`
    *   `critic: Callable[[Artifact, dict], CriticReport]`
    *   `auditor: Callable[[List[TraceEntry]], AuditReport] | None`
    *   `verifier: Callable[[Artifact], dict]`
    *   `state_machine: StateMachine`
    *   `metrics_evaluator: Callable[[List[TraceEntry]], ProcessMetrics]`
    *   `policy_engine: PolicyEngine`
    *   `config: Dict`
2.  Метод `process_task(spec, context) -> TaskResult`:
    *   Инициализирует `trace = []` **локально** (не в self!).
    *   Цикл while status == IN_PROGRESS.
    *   На каждой итерации:
        1.  Вызов кодера. Обработка исключений → эскалация.
        2.  Вызов верификатора. Обработка таймаутов.
        3.  **Policy Check (Pre-Critic).** Если BLOCK → эскалация. Если RETRY → перезапуск кодера с флагом.
        4.  Вызов критика.
        5.  Запись в trace.
        6.  Вычисление метрик.
        7.  Проверка Stop Criteria (Pass/User/Limit).
        8.  Проверка Audit Triggers (N iters/Stagnation/Ambiguous).
        9.  Если аудит вызван → `audit_result`. Если block → эскалация.
        10. Обновление канбана (через state_machine).
    *   Возвращает `TaskResult(status, artifact, trace, metrics_history)`.
3.  **Логирование:** Каждый шаг цикла должен писать структурированный лог (JSON line).
4.  **Обработка ошибок:** Любое необработанное исключение внутри цикла должно приводить к безопасной остановке и сохранению текущего trace.

---

## 4. Критерии приемки (Definition of Done)

### 4.1. Функциональные
- [ ] State Machine блокирует все нелегальные переходы (покрыто property-based тестами).
- [ ] Metrics Evaluator корректно считает все 7 метрик на синтетических трассах.
- [ ] Policy Engine детектирует модификацию тестов и косметические правки.
- [ ] Orchestrator выполняет полный цикл с заглушками за < 100ms (без I/O).
- [ ] Orchestrator корректно останавливается по всем 4 stop-criteria.
- [ ] Trace сохраняется полностью даже при ошибке в середине цикла.

### 4.2. Тестовые
- [ ] Unit-тесты покрытия ≥ 90% для state_machine и metrics_evaluator.
- [ ] Integration-тест оркестратора с mock-зависимостями.
- [ ] Тесты на стагнацию: подать трассу с осцилляцией → получить trigger.
- [ ] Тесты на anti-hack: подать артефакт с измененным тестом → получить block.
- [ ] Property-based тесты для State Machine (Hypothesis: random transitions never crash).

### 4.3. Структурные
- [ ] Нет глобального состояния (все state в локальных переменных или передаваемых объектах).
- [ ] Нет прямых импортов реализаций агентов (только Protocols/Callables).
- [ ] Конфигурация порогов вынесена в dataclass/config object.
- [ ] Type hints полные, mypy strict passes.

---

## 5. Риски и митигации

| Риск | Вероятность | Влияние | Митигация |
| :--- | :--- | :--- | :--- |
| Metrics Evaluator падает на битых данных | Средняя | Остановка цикла | Defensive coding: try/except вокруг каждой метрики + дефолтные значения. |
| Policy Engine дает ложноположительные блокировки | Высокая | Блокировка валидных задач | Конфигурируемые пороги. Флаг `strict_mode` (off by default). Логирование причин блока. |
| Orchestrator уходит в бесконечный цикл | Низкая | Зависание | Жесткий `max_iterations` + watchdog timer на уровне процесса. |
| Смешение логики аудита и политики | Средняя | Дублирование | Code review. Policy = sync/fast/deterministic. Audit = async/slow/heuristic. |
| Trace растет слишком быстро | Средняя | OOM | Хранить только hash артефакта в trace, полные артефакты — в отдельном storage/cache. |

---

## 6. Порядок выполнения

1.  Реализовать `state_machine.py` + тесты (Property-based).
2.  Реализовать `metrics_evaluator.py` + тесты (Golden master).
3.  Реализовать `policy_engine.py` + тесты (Edge cases).
4.  Реализовать `orchestrator.py` с использованием заглушек.
5.  Написать integration-тест полного цикла.
6.  Добавить структурированное логирование.
7.  Прогнать mypy + coverage.
8.  Открыть PR.

---

## 7. Ссылки и контекст
*   WP-0 Спецификация: `docs/WP0_SPEC.md`
*   Архитектурные решения: `docs/ARCHITECTURE.md` §"Разделение ролей"
*   План реализации: `docs/TASKS.md` §"Эпик 1"
*   АРИЗ-анализ слабых мест: `docs/ариз.txt` §"Слабые места схемы"

---

**Примечание для ревьюера:** При проверке PR обращать особое внимание на **отсутствие side-effects в Metrics Evaluator** и **локальность trace в Orchestrator**. Любое использование `self.trace` или глобальных переменных для хранения состояния задачи — **блокирующее замечание**. Также проверить, что Policy Engine НЕ принимает решений о *качестве кода*, только о *соблюдении правил*.
