"""
Высокоуровневые операции канбан-доски.
"""

import hashlib
import uuid
from typing import Optional, List, Dict, Any
from .models import Task, TaskStatus
from .storage import KanbanStorage


class KanbanOperations:
    """Операции канбан-доски"""

    def __init__(self, storage: Optional[KanbanStorage] = None):
        self.storage = storage or KanbanStorage()

    # ── создание ──

    def create_task(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        mode: str = "sufficiency",
        max_iterations: Optional[int] = None,
        task_id: Optional[str] = None,
        fact_pack: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Создание новой задачи с уникальным ID.

        Args:
            query: Исходный запрос пользователя
            context: Контекст задачи
            mode: sufficiency | optimality
            max_iterations: Максимум итераций (по умолчанию из mode)
            task_id: ID задачи (если None, генерируется автоматически)
            fact_pack: Структурированный входной пакет (FactPack)

        Returns:
            Task: Созданная задача
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        if max_iterations is None:
            max_iterations = 3 if mode == "sufficiency" else 5

        task = Task(
            id=task_id,
            query=query,
            context=context or {},
            status=TaskStatus.QUEUE,
            mode=mode,
            max_iterations=max_iterations,
            fact_pack=fact_pack,
        )
        self.storage.save_task(task)
        return task

    # ── перемещение по колонкам ──

    def move_task(self, task_id: str, new_status: TaskStatus) -> bool:
        task = self.storage.load_task(task_id)
        if not task:
            return False
        task.update_status(new_status)
        self.storage.save_task(task)
        return True

    # ── получение ──

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.storage.load_task(task_id)

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        return self.storage.load_tasks_by_status(status)

    def get_queue_tasks(self) -> List[Task]:
        return self.get_tasks_by_status(TaskStatus.QUEUE)

    def get_in_progress_tasks(self) -> List[Task]:
        result = []
        for s in (TaskStatus.GENERATOR, TaskStatus.CRITIC, TaskStatus.REWORK):
            result.extend(self.get_tasks_by_status(s))
        return result

    def get_done_tasks(self) -> List[Task]:
        return self.get_tasks_by_status(TaskStatus.DONE)

    def delete_task(self, task_id: str):
        self.storage.delete_task(task_id)

    def update_task_iteration(self, task_id: str, iteration_data: Dict[str, Any]):
        """
        Обновить задачу данными итерации (без увеличения current_iteration).
        Используется в run_triz_cycle для записи промежуточных итераций.
        """
        task = self.storage.load_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.iterations.append(iteration_data)
        self.storage.save_task(task)

    def complete_task(self, task_id: str, result: Dict[str, Any]):
        task = self.storage.load_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.result = result
        task.update_status(TaskStatus.DONE)
        self.storage.save_task(task)

    def fail_task(self, task_id: str, error: str):
        task = self.storage.load_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.error = error
        task.update_status(TaskStatus.FAILED)
        self.storage.save_task(task)

    
