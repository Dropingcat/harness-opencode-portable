"""
Канбан-модуль для ТРИЗ-агента.
Управляет жизненным циклом задач через внешнюю доску.
"""

from .models import Task, TaskStatus
from .storage import KanbanStorage
from .operations import KanbanOperations

__all__ = ['Task', 'TaskStatus', 'KanbanStorage', 'KanbanOperations']