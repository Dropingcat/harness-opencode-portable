Ниже представлено техническое задание для разработчика на блок **WP-0: Фундамент и Контракты**. Документ составлен в формальном стиле, содержит жесткие требования к структуре, логике и валидации, а также учитывает все согласованные архитектурные решения (разделение ролей, детерминизм, безопасность).

Этот документ можно напрямую передать исполнителю.

---

# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: WP-0 «Фундамент и Контракты»
**Проект:** Agent-Kirpichik  
**Версия спецификации:** 0.2  
**Приоритет:** 🔴 Critical (Блокирующий)  
**Ожидаемое время выполнения:** 2–3 дня  

## 1. Цели и границы ответственности
**Цель:** Создать неизменяемый базис типов данных, интерфейсов и схем валидации, который будет использоваться всеми последующими модулями (WP-1…WP-4).  
**Границы:**
*   ✅ **Входит:** Pydantic-модели, JSON Schemas, Protocols (интерфейсы), Enum’ы, утилиты сериализации.
*   ❌ **Не входит:** Бизнес-логика, реализация агентов, оркестрация, LLM-вызовы, тесты интеграции.

> ⚠️ **Критическое ограничение:** Код этого блока НЕ должен содержать импортов `openai`, `anthropic`, `docker`, `subprocess` (кроме типизации) и любых других тяжелых зависимостей. Только `pydantic`, `typing`, `enum`, `datetime`, `json`.

---

## 2. Артефакты и структура файлов

```text
src/core/
├── __init__.py
├── types.py            # Enum'ы и базовые алиасы
├── models.py           # Pydantic модели данных
├── protocols.py        # Интерфейсы (Sandbox, LLM, Agents)
└── serialization.py    # Утилиты для datetime/JSON

contracts/schemas/
├── context.schema.json
├── artifact.schema.json
├── critic_report.schema.json
├── audit_report.schema.json
├── trace.schema.json
└── process_metrics.schema.json
```

---

## 3. Детальные требования к моделям (`models.py`)

### 3.1. Общие правила
1.  Использовать **только Pydantic v2** (`BaseModel`). Dataclasses запрещены (нет встроенной валидации/сериализации).
2.  Все модели должны быть `frozen=True` (immutable) где возможно.
3.  Поля с датами: **только `datetime`**, сериализация в ISO8601 через кастомный конфиг или serializer.
4.  Запретить лишние поля: `model_config = ConfigDict(extra='forbid')` для всех входных контрактов.
5.  Обязательные поля не должны иметь дефолтных значений (кроме коллекций).

### 3.2. Перечень моделей и полей

#### `TaskContext` (Входной контекст задачи)
| Поле | Тип | Обяз. | Описание | Валидация |
| :--- | :--- | :--- | :--- | :--- |
| `files` | `Dict[str, str]` | Да | Путь → содержимое. Ключи — относительные пути. | Regex ключа: `^[a-zA-Z0-9_./-]+$` |
| `dependencies` | `List[str]` | Нет | Список пакетов/модулей. | Уникальность элементов |
| `constraints` | `Dict[str, Any]` | Нет | Ограничения (timeout, memory). | Доп. ключи только из whitelist |
| `metadata` | `Dict[str, str]` | Нет | Произвольные метаданные. | Значения только строки |

#### `Artifact` (Результат работы кодера)
| Поле | Тип | Обяз. | Описание |
| :--- | :--- | :--- | :--- |
| `files` | `Dict[str, str]` | Да | Аналогично TaskContext |
| `reasoning` | `str \| None` | Нет | Краткое обоснование изменений (для логов, не для критика) |
| `created_at` | `datetime` | Да | Автозаполнение, ISO8601 |

#### `CriticReport` (ТОЛЬКО результат, БЕЗ процесса)
| Поле | Тип | Обяз. | Описание |
| :--- | :--- | :--- | :--- |
| `verdict` | `Verdict` | Да | PASS / FAIL / AMBIGUOUS |
| `findings` | `List[Finding]` | Да | Список замечаний. Пустой при PASS |
| `requires_user` | `bool` | Да | True только если verdict=AMBIGUOUS |
| `decision_question` | `str \| None` | Нет | Обязан быть заполнен если requires_user=True |
| `uncertainty_score` | `float` | Да | [0.0, 1.0]. Оценка неуверенности критика |

> ❗ **ВАЖНО:** В `CriticReport` **ЗАПРЕЩЕНЫ** поля: `process_violations`, `hack_detected`, `lazy_detected`, `trace_analysis`. Это зона ответственности аудитора.

#### `AuditReport` (ТОЛЬКО процесс, БЕЗ оценки кода)
| Поле | Тип | Обяз. | Описание |
| :--- | :--- | :--- | :--- |
| `compliant` | `bool` | Да | Соответствует ли исполнение регламенту |
| `violations` | `List[ProcessViolation]` | Да | Список нарушений процесса |
| `block` | `bool` | Да | Требует ли остановку цикла |
| `block_reason` | `str \| None` | Нет | Обязан быть заполнен если block=True |
| `recommendations` | `List[str]` | Нет | Рекомендации по процессу (не по коду!) |

> ❗ **ВАЖНО:** В `AuditReport` **ЗАПРЕЩЕНЫ** поля: `findings`, `verdict`, `code_quality_score`, `fix_suggestions`.

#### `ProcessMetrics` (Детерминированные метрики)
| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `log_completeness` | `float` | [0.0, 1.0] Полнота логов |
| `trace_integrity` | `bool` | Целостность цепочки итераций |
| `semantic_diff_ratio` | `float` | [0.0, 1.0] Доля значимых изменений |
| `fix_repetition_rate` | `float` | [0.0, 1.0] Частота повторов fix_notes |
| `iteration_time_variance` | `float` | Дисперсия времени итераций |
| `tool_usage_consistency` | `bool` | Соблюдение обязательных инструментов |
| `contract_violations_count` | `int` | ≥ 0 Нарушения схем входа/выхода |

#### `TraceEntry`
| Поле | Тип | Обяз. | Примечание |
| :--- | :--- | :--- | :--- |
| `iteration` | `int` | Да | ≥ 1, монотонно возрастает |
| `timestamp` | `datetime` | Да | ISO8601 |
| `artifact_hash` | `str` | Да | SHA256 от Artifact.files |
| `tool_results_summary` | `Dict` | Нет | Агрегированные результаты |
| `critic_verdict` | `Verdict` | Да | Для быстрого анализа |
| `metrics_snapshot` | `ProcessMetrics` | Нет | Снимок метрик на момент итерации |

> ⚠️ **Оптимизация:** В TraceEntry храним `artifact_hash`, а не полный артефакт. Полный артефакт хранится отдельно или в первом/последнем entry. Это предотвращает раздувание трассы.

---

## 4. Требования к интерфейсам (`protocols.py`)

Использовать `typing.Protocol` (runtime-checkable).

### 4.1. `SandboxRunner`
```python
class SandboxRunner(Protocol):
    def execute(self, code: str, files: Dict[str, str], 
                timeout_sec: int) -> ExecutionResult: ...
    def cleanup(self) -> None: ...
```
*   `ExecutionResult` должен содержать: `stdout`, `stderr`, `exit_code`, `timed_out: bool`, `resource_usage: Dict`.
*   Метод `execute` **НЕ** должен бросать исключения при ошибке выполнения кода — только при ошибке инфраструктуры.

### 4.2. `LLMProvider`
```python
class LLMProvider(Protocol):
    async def complete(self, messages: List[Message], 
                       response_schema: Type[T]) -> LLMResponse[T]: ...
```
*   `LLMResponse` должен содержать: `data: T`, `usage: TokenUsage`, `model: str`, `latency_ms: float`.
*   Поддержка generic type для структурированного вывода.

### 4.3. `Agent` (базовый протокол для Coder/Critic/Auditor)
```python
class Agent(Protocol):
    @property
    def name(self) -> str: ...
    
    @property
    def input_schema(self) -> Type[BaseModel]: ...
    
    @property
    def output_schema(self) -> Type[BaseModel]: ...
```

---

## 5. Требования к JSON Schema (`contracts/schemas/`)

1.  Генерировать автоматически из Pydantic-моделей через `model.model_json_schema()`.
2.  Добавить скрипт `scripts/generate_schemas.py` который:
    *   Импортирует все модели
    *   Генерирует JSON Schema
    *   Записывает в `contracts/schemas/`
    *   Проверяет, что файл изменился (для CI)
3.  Схемы должны включать `description` для каждого поля (берется из docstring/model Field).
4.  Версионирование: добавить поле `$schema_version` в каждую схему.

---

## 6. Критерии приемки (Definition of Done)

### 6.1. Функциональные
- [ ] Все модели проходят валидацию на 10+ позитивных и 10+ негативных примерах
- [ ] Сериализация/десериализация datetime работает корректно (round-trip test)
- [ ] `extra='forbid'` блокирует неизвестные поля
- [ ] JSON Schema генерируются и соответствуют моделям
- [ ] Protocols проверяются через `isinstance()` с runtime-checkable

### 6.2. Структурные
- [ ] Нет циклических импортов
- [ ] Нет внешних зависимостей кроме pydantic/stdlib
- [ ] Все публичные классы/функции имеют docstrings
- [ ] Type hints полные (mypy strict mode passes)

### 6.3. Тестовые
- [ ] Unit-тесты покрытия ≥ 95% (logic coverage)
- [ ] Property-based тесты (Hypothesis) для сериализации
- [ ] Тесты на immutability моделей
- [ ] Тесты на валидацию граничных значений

---

## 7. Риски и митигации

| Риск | Митигация |
| :--- | :--- |
| Разработчик добавит бизнес-логику в модели | Code review + lint правило "no methods with side effects in models" |
| Несовместимость Pydantic v1/v2 | Зафиксировать `pydantic>=2.0,<3.0` в requirements |
| Схемы устаревают при изменении моделей | CI check: `generate_schemas.py --check` fails if diff |
| DateTime сериализация ломается при передаче между сервисами | Единый формат ISO8601 + timezone-aware everywhere |
| Protocol не проверяется в runtime | Использовать `@runtime_checkable` + тесты isinstance |

---

## 8. Порядок выполнения

1.  Настроить проект: `pyproject.toml`, mypy, pytest, hypothesis.
2.  Реализовать `types.py` (Enum'ы).
3.  Реализовать `serialization.py` (datetime utils).
4.  Реализовать модели в порядке зависимостей: Context → Artifact → Finding → CriticReport/AuditReport → ProcessMetrics → TraceEntry.
5.  Написать unit-тесты для каждой модели **ДО** перехода к следующей.
6.  Реализовать `protocols.py`.
7.  Написать `scripts/generate_schemas.py`.
8.  Сгенерировать схемы и закоммитить.
9.  Прогнать полный тестовый suite.
10. Открыть PR с описанием принятых решений.

---

## 9. Ссылки и контекст
*   Архитектурные решения: см. протокол встречи от [дата]
*   Оригинальная спецификация: `docs/план.txt` §2
*   АРИЗ-анализ: `docs/ариз.txt` §"Слабые места схемы"
*   Scrum-план: `docs/Scrum_Agile.txt` §"Эпик 0"

---

**Примечание для ревьюера:** При проверке PR обращать особое внимание на **отсутствие смешения ролей** в моделях. Любое поле в CriticReport, относящееся к процессу, или поле в AuditReport, относящееся к качеству кода — это **блокирующее замечание**.
