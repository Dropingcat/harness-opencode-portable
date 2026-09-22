# THREAT_MODEL.md: Безопасность системы v0.2

> ⚠️ **СТАТУС:** ОБЯЗАТЕЛЬНО К ОЗНАКОМЛЕНИЮ ДЛЯ ВСЕХ РАЗРАБОТЧИКОВ.

## 1. Trust Boundaries
1.  **Host System:** Доверенная зона. Содержит API-ключи, конфиги, оркестратор.
2.  **Sandbox:** Враждебная зона. Исполняет пользовательский/сгенерированный код.
3.  **LLM Provider:** Внешний доверенный сервис. Передает промты, получает ответы.
4.  **User Input:** Недоверенные данные. Спецификации, контекст, ответы на эскалацию.

## 2. Assets & Threats

| Asset | Threat | Severity | Mitigation | Status |
| :--- | :--- | :--- | :--- | :--- |
| Host FS | Sandbox Escape | Critical | Docker `read_only`, `no-new-privileges`, RLIMITs | ✅ Planned |
| API Keys | Leakage | Critical | Env vars only, log redaction, secret scanning | ✅ Planned |
| CPU/RAM | Resource Exhaustion | High | RLIMIT_CPU/AS/NPROC, Docker limits, timeouts | ✅ Planned |
| Network | Data Exfiltration | High | `network_mode=none`, firewall rules | ✅ Planned |
| LLM Budget | Cost Overrun | Medium | Pre-check budget, hard limit per task, alerts | ✅ Planned |
| Trace Data | Privacy Leak | Medium | No PII in logs, retention policy | ⏳ Backlog |
| Verifier | Command Injection | High | Parameterized execution, no shell=True | ✅ Planned |

## 3. Security Requirements

### 3.1. Sandbox (Local & Docker)
-   **FAIL CLOSED:** При ошибке создания изоляции код НЕ выполняется.
-   **NO NETWORK:** Полная изоляция сети по умолчанию.
-   **CLEANUP:** Гарантированное удаление ресурсов через context manager / auto_remove.
-   **NO SHELL:** Запуск инструментов только через массив аргументов, никогда через строку.

### 3.2. LLM Gateway
-   **NO SECRETS IN CODE:** Ключи только через env/secret manager.
-   **LOG REDACTION:** Промты и ответы не логируются в plaintext.
-   **BUDGET PRE-CHECK:** Проверка лимита ДО вызова API.
-   **INPUT SANITIZATION:** Очистка user input перед включением в промт.

### 3.3. Verifier
-   **PARSER SAFETY:** Никаких `eval()`, `exec()`, `yaml.load()` без SafeLoader.
-   **RAW OUTPUT PRESERVATION:** При ошибке парсинга сохранять сырой вывод для отладки.
-   **TOOL ISOLATION:** Инструменты запускаются ВНУТРИ sandbox, не на хосте.

## 4. Incident Response
1.  При обнаружении sandbox escape: немедленно остановить все задачи, изолировать хост, сохранить логи.
2.  При утечке ключей: отозвать ключи, проверить логи доступа, ротировать все секреты.
3.  При превышении бюджета: автоматическая блокировка LLM-вызовов, алерт владельцу.

## 5. Review Cadence
-   Перед каждым релизом.
-   При изменении архитектуры sandbox/LLM.
-   После любого инцидента безопасности.
