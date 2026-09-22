#!/bin/bash
# kanban-board — посмотреть глобальную доску
# Использование:
#   kanban-board                  — все последние статусы
#   kanban-board triz-agent       — фильтр по группе
#   kanban-board triz-agent triz-coder  — конкретный агент
#   kanban-board --summary        — краткая сводка (Telegram-ready)

KANBAN_DIR="/home/orangepi/.hermes/kanban"
PYTHON_CMD="${KANBAN_DIR}/global_kanban.py"

if [ ! -f "$PYTHON_CMD" ]; then
    echo "❌ Ошибка: $PYTHON_CMD не найден"
    exit 1
fi

if [ "$1" = "--summary" ]; then
    python3 "$PYTHON_CMD"
else
    python3 "$PYTHON_CMD" board "$@"
fi
exit $?