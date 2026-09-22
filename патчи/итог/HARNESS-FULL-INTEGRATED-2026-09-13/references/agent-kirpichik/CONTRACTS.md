# CONTRACTS.md: Спецификация контрактов данных v0.2

> ⚠️ **СТАТУС:** УТВЕРЖДЕНО. Изменения только через RFC.
> Все модели реализуются через Pydantic v2. Dataclasses запрещены.

## 1. Общие правила
1.  **Immutable:** Все модели `frozen=True`, кроме `TaskState`.
2.  **Strict:** `extra='forbid'` для всех входных контрактов.
3.  **DateTime:** Только `datetime` с timezone, сериализация ISO8601.
4.  **Validation:** Каждая модель имеет unit-тесты на позитивные/негативные кейсы.

## 2. Модели данных

### 2.1. TaskContext (Входной контекст)
| Поле | Тип | Обяз. | Описание | Валидация |
| :--- | :--- | :--- | :--- | :--- |
| `files` | `Dict[str, str]` | Да | Путь → содержимое | Regex ключа: `^[a-zA-Z0-9_./-]+$` |
| `dependencies` | `List[str]` | Нет | Список пакетов | Уникальность |
| `constraints` | `Dict[str, Any]` | Нет | Ограничения | Whitelist ключей |
| `metadata` | `Dict[str, str]` | Нет | Метаданные | Значения только строки |

### 2.2. Artifact (Результат кодера)
| Поле | Тип | Обяз. | Описание |
| :--- | :--- | :--- | :--- |
| `files` | `Dict[str, str]` | Да | Файлы артефакта |
| `reasoning` | `str \| None` | Нет | Обоснование (для логов) |
| `created_at` | `datetime` | Да | Время создания |

### 2.3. CriticReport (ТОЛЬКО РЕЗУЛЬТАТ)
> ❗ **ЗАПРЕЩЕНЫ ПОЛЯ:** `process_violations`, `hack_detected`, `trace_analysis`.

| Поле | Тип | Обяз. | Описание |
| :--- | :--- | :--- | :--- |
| `verdict` | `Verdict` | Да | PASS / FAIL / AMBIGUOUS |
| `findings` | `List[Finding]` | Да | Список замечаний |
| `requires_user` | `bool` | Да | Флаг эскалации |
| `decision_question` | `str \| None` | Нет | Вопрос пользователю |
| `uncertainty_score` | `float` | Да | [0.0, 1.0] Неуверенность критика |

### 2.4. AuditReport (ТОЛЬКО ПРОЦЕСС)
> ❗ **ЗАПРЕЩЕНЫ ПОЛЯ:** `findings`, `verdict`, `code_quality_score`, `fix_suggestions`.

| Поле | Тип | Обяз. | Описание |
| :--- | :--- | :--- | :--- |
| `compliant` | `bool` | Да | Соответствие регламенту |
| `violations` | `List[ProcessViolation]` | Да | Нарушения процесса |
| `block` | `bool` | Да | Требование остановки |
| `block_reason` | `str \| None` | Нет | Причина блока |
| `recommendations` | `List[str]` | Нет | Процессные рекомендации |

### 2.5. ProcessMetrics (Детерминированные)
| Поле | Тип | Диапазон | Описание |
| :--- | :--- | :--- | :--- |
| `log_completeness` | `float` | [0, 1] | Полнота логов |
| `trace_integrity` | `bool` | - | Целостность трассы |
| `semantic_diff_ratio` | `float` | [0, 1] | Доля значимых изменений |
| `fix_repetition_rate` | `float` | [0, 1] | Осцилляция фиксов |
| `iteration_time_variance` | `float` | ≥ 0 | Дисперсия времени |
| `tool_usage_consistency` | `bool` | - | Стабильность верификатора |
| `contract_violations_count` | `int` | ≥ 0 | Нарушения схем |

### 2.6. TraceEntry
| Поле | Тип | Обяз. | Примечание |
| :--- | :--- | :--- | :--- |
| `iteration` | `int` | Да | ≥ 1, монотонно |
| `timestamp` | `datetime` | Да | ISO8601 |
| `artifact_hash` | `str` | Да | SHA256 от Artifact.files |
| `critic_verdict` | `Verdict` | Да | Для быстрого анализа |
| `metrics_snapshot` | `ProcessMetrics` | Нет | Снимок метрик |

## 3. JSON Schema Generation
Схемы генерируются автоматически скриптом `scripts/generate_schemas.py`.
Ручное редактирование `.json` файлов запрещено.
