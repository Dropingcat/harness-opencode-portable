# Runtime Integration Capsule

Runtime Integration Capsule — это финальный слой, который связывает все готовые капсулы в работающий OpenCode модуль. Он управляет жизненным циклом плагинов, MCP серверов, окружением и путями.

## 1. Назначение

Runtime Integration Capsule — это **функциональный фасад** для запуска модуля как полноценного OpenCode модуля. Он не содержит бизнес-логики, а оркестрирует:

- Регистрацию/дерегистрацию плагинов
- Жизненный цикл MCP серверов
- Разрешение окружения и переменных
- Исправление путей в конфигах/агентах
- Проверку готовности (health checks)

## 2. Область ответственности

| Область | Что делает |
|---------|------------|
| **Plugin Lifecycle** | Установка/удаление/обновление плагинов в opencode.jsonc |
| **MCP Lifecycle** | Запуск/остановка/health-check 4 MCP серверов |
| **Environment** | Загрузка/валидация OPENCODE_HARNESS_ROOT, OPENCODE_SESSION_DB, DOC_GUARD_ENTRYPOINT, OPENCODE_RUNS_DIR |
| **Path Resolution** | Замена хардкодов /home/orangepi -> env vars в agents/launchers/configs |
| **Health Checks** | Проверка готовности: plugin загружен, MCP отвечают, guard работает, DB доступна |

## 3. Архитектура

`
Runtime Integration Capsule
├── Plugin Manager
│   ├── register_plugin()
│   ├── unregister_plugin()
│   └── update_plugin()
├── MCP Manager
│   ├── start_servers()
│   ├── stop_servers()
│   └── health_check()
├── Environment Resolver
│   ├── load_env()
│   ├── validate_required()
│   └── resolve_paths()
├── Path Resolver
│   ├── scan_configs()
│   ├── replace_hardcoded()
│   └── write_back()
└── Health Checker
    ├── check_plugin()
    ├── check_mcp()
    ├── check_guard()
    └── check_db()
`

## 4. Контракты

### Вход
- config/runtime_integration_policy.json — политики интеграции
- config/opencode_plugin_config.json — конфиг плагина
- config/mcp_lifecycle_config.json — конфиг MCP lifecycle
- config/path_resolution_map.json — мапа путей для замены

### Выход
- Обновлённый opencode.jsonc
- Запущенные MCP процессы
- Исправленные конфиги/агенты
- Health check отчёт

## 5. Инварианты

- Все пути разрешаются через env vars, не хардкод
- Все сервисы управляются детерминированно
- Состояние сохраняется в JSON, не в памяти
- Ошибки не молчат — выбрасываются с кодом причины
