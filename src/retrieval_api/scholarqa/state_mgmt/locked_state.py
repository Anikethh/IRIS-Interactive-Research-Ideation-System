from typing import Type

from nora_lib.tasks.models import AsyncTaskState, R
from nora_lib.tasks.state import StateManager
from filelock import FileLock


class LockedStateManager(StateManager):
    def __init__(self, task_state_class: Type[AsyncTaskState[R]], state_dir) -> None:
        super().__init__(task_state_class, state_dir)

    def read_state(self, task_id: str) -> AsyncTaskState[R]:
        lock = FileLock(f"{task_id}.lock")
        with lock:
            return super().read_state(task_id)

    def write_state(self, state: AsyncTaskState[R]) -> None:
        lock = FileLock(f"{state.task_id}.lock")
        with lock:
            super().write_state(state)
