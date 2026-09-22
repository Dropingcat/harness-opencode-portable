#!/bin/bash
# kanban-report — агент отчитывается в глобальный канбан
# Использование:
#   kanban-report <agent_id> <task_name> [status] [progress] [message]
#
# Примеры:
#   kanban-report triz-coder "Phase C" WORKING "3/8" "рефакторинг core.py"
#   kanban-report weather-bot "Деплой" DONE "" "все сервисы запущены"
#   kanban-report bridge-bogdan "Настройка" BLOCKED "" "ждём токен от Bogdan"

KANBAN_DIR="/home/orangepi/.hermes/kanban"
PYTHON_CMD="${KANBAN_DIR}/global_kanban.py"

if [ ! -f "$PYTHON_CMD" ]; then
    echo "❌ Ошибка: $PYTHON_CMD не найден"
    echo "Проверь: ~/.hermes/kanban/global_kanban.py"
    exit 1
fi

python3 "$PYTHON_CMD" report "$@"
exit $?