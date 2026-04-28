from __future__ import annotations

import contextlib
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator, List, Optional, TextIO


def _validate_task_common(task_id: int, priority: int, duration: int) -> None:
    if task_id < 0:
        raise ValueError("ID must be non-negative")
    if not 1 <= priority <= 10:
        raise ValueError("Priority must be in range 1..10")
    if duration <= 0:
        raise ValueError("Duration must be positive")


@dataclass
class Task(ABC):
    task_id: int
    task_text: str
    assignee: str
    priority: int
    duration: int

    def __post_init__(self) -> None:
        _validate_task_common(self.task_id, self.priority, self.duration)

    def getId(self) -> int:
        return self.task_id

    def getText(self) -> str:
        return self.task_text

    def getAssignee(self) -> str:
        return self.assignee

    def getPriority(self) -> int:
        return self.priority

    def getDuration(self) -> int:
        return self.duration

    def changePriority(self, new_priority: int) -> None:
        if not 1 <= new_priority <= 10:
            raise ValueError("Priority must be in range 1..10")
        self.priority = new_priority

    @abstractmethod
    def getNextExecutionTime(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def execute(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def displayInfo(self) -> None:
        raise NotImplementedError


@dataclass
class DeadlineTask(Task):
    deadline: int

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.deadline < 0:
            raise ValueError("Deadline must be non-negative")

    def getDeadline(self) -> int:
        return self.deadline

    def extendDeadline(self, extra_time: int) -> None:
        if extra_time < 0:
            raise ValueError("Deadline extension must be non-negative")
        self.deadline += extra_time

    def getNextExecutionTime(self) -> int:
        return self.deadline

    def execute(self) -> None:
        print(
            f"[EXECUTE][Deadline] ID={self.task_id} | '{self.task_text}' | "
            f"Assignee={self.assignee} | Deadline={self.deadline}s"
        )

    def displayInfo(self) -> None:
        print(
            f"DeadlineTask(ID={self.task_id}, text='{self.task_text}', assignee='{self.assignee}', "
            f"priority={self.priority}, duration={self.duration}s, deadline={self.deadline}s)"
        )


@dataclass
class PeriodicTask(Task):
    next_execution: int
    period: int

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.next_execution < 0:
            raise ValueError("First execution time must be non-negative")
        if self.period <= 0:
            raise ValueError("Period must be positive")

    def getNextExecution(self) -> int:
        return self.next_execution

    def getPeriod(self) -> int:
        return self.period

    def skipNextExecution(self) -> None:
        self.next_execution += self.period

    def getNextExecutionTime(self) -> int:
        return self.next_execution

    def execute(self) -> None:
        print(
            f"[EXECUTE][Periodic] ID={self.task_id} | '{self.task_text}' | "
            f"Assignee={self.assignee} | NextRun={self.next_execution}s | Period={self.period}s"
        )

    def displayInfo(self) -> None:
        print(
            f"PeriodicTask(ID={self.task_id}, text='{self.task_text}', assignee='{self.assignee}', "
            f"priority={self.priority}, duration={self.duration}s, nextExecution={self.next_execution}s, "
            f"period={self.period}s)"
        )


@dataclass
class OverdueTask(Task):
    def getNextExecutionTime(self) -> int:
        return 0

    def canExecute(self, current_priority: int) -> bool:
        return self.priority >= current_priority

    def execute(self) -> None:
        print(
            f"[EXECUTE][Overdue] ID={self.task_id} | '{self.task_text}' | "
            f"Assignee={self.assignee} | Requires immediate action"
        )

    def displayInfo(self) -> None:
        print(
            f"OverdueTask(ID={self.task_id}, text='{self.task_text}', assignee='{self.assignee}', "
            f"priority={self.priority}, duration={self.duration}s, status='immediate')"
        )


class Plan:
    def __init__(self) -> None:
        self.tasks: List[Task] = []

    def addTask(self, task: Task) -> None:
        if task is None:
            raise ValueError("Cannot add empty task")
        self.tasks.append(task)
        print(f"Task added: ID={task.getId()}")

    def removeTask(self, task_id: int) -> bool:
        for idx, task in enumerate(self.tasks):
            if task.getId() == task_id:
                del self.tasks[idx]
                return True
        return False

    def getTask(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.getId() == task_id:
                return task
        return None

    def getTasksByAssignee(self, assignee: str) -> List[Task]:
        return [task for task in self.tasks if task.getAssignee() == assignee]

    def getNextTask(self) -> Optional[Task]:
        if not self.tasks:
            return None
        return min(self.tasks, key=lambda task: task.getNextExecutionTime())

    def executeNextTask(self) -> None:
        next_task = self.getNextTask()
        if next_task is None:
            print("No tasks to execute")
            return

        next_task.execute()
        if isinstance(next_task, PeriodicTask):
            next_task.skipNextExecution()
            print(
                f"PeriodicTask ID={next_task.getId()} rescheduled to "
                f"{next_task.getNextExecutionTime()}s"
            )
        else:
            self.removeTask(next_task.getId())
            print(f"Task ID={next_task.getId()} removed from plan")

    def getAllTasks(self) -> List[Task]:
        return list(self.tasks)

    def isEmpty(self) -> bool:
        return len(self.tasks) == 0

    def getTaskCount(self) -> int:
        return len(self.tasks)

    def displayAllTasks(self) -> None:
        if not self.tasks:
            print("Plan is empty")
            return
        for task in self.tasks:
            task.displayInfo()


class Scheduler:
    def __init__(self) -> None:
        self.plan = Plan()

    def addTask(self, task: Task) -> None:
        if task is None:
            raise ValueError("Received empty task")
        self.plan.addTask(task)

    def buildOptimalPlan(self, tasks: List[Task]) -> None:
        sorted_tasks = sorted(tasks, key=lambda task: task.getNextExecutionTime())
        for task in sorted_tasks:
            self.addTask(task)
        print(f"Optimal plan built. Tasks added: {len(sorted_tasks)}")

    def addDeadlineTask(
        self, task_id: int, text: str, worker: str, priority: int, duration: int, deadline: int
    ) -> None:
        self.addTask(DeadlineTask(task_id, text, worker, priority, duration, deadline))

    def addPeriodicTask(
        self,
        task_id: int,
        text: str,
        worker: str,
        priority: int,
        duration: int,
        next_execution: int,
        period: int,
    ) -> None:
        self.addTask(PeriodicTask(task_id, text, worker, priority, duration, next_execution, period))

    def addOverdueTask(self, task_id: int, text: str, worker: str, priority: int, duration: int) -> None:
        self.addTask(OverdueTask(task_id, text, worker, priority, duration))

    def executeNext(self) -> None:
        self.plan.executeNextTask()

    def getAssigneeTasks(self, assignee: str) -> List[Task]:
        return self.plan.getTasksByAssignee(assignee)

    def displayPlan(self) -> None:
        print("=== CURRENT PLAN ===")
        print(f"Task count: {self.plan.getTaskCount()}")
        next_task = self.plan.getNextTask()
        if next_task:
            print(
                f"Next task: ID={next_task.getId()}, "
                f"time={next_task.getNextExecutionTime()}s"
            )
        else:
            print("Next task: none")
        self.plan.displayAllTasks()
        print("====================")

    def run(self, max_steps: Optional[int] = None) -> None:
        print("Scheduler started...")
        steps = 0
        while not self.plan.isEmpty():
            self.executeNext()
            steps += 1
            # Prevent infinite loop when plan contains only periodic tasks.
            if max_steps is not None and steps >= max_steps:
                print(f"Stopped by step limit ({max_steps})")
                return
        print("All tasks are completed")


@contextlib.contextmanager
def ostream_redirect(
    stdout: bool = True,
    stderr: bool = True,
    target: Optional[TextIO] = None,
) -> Generator[None, None, None]:
    """
    Совместимый контекстный менеджер с pybind11 ostream_redirect.
    По умолчанию перенаправляет в текущий sys.stdout/sys.stderr.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stream = target or old_stdout
    try:
        if stdout:
            sys.stdout = stream
        if stderr:
            sys.stderr = stream
        yield
    finally:
        if stdout:
            sys.stdout = old_stdout
        if stderr:
            sys.stderr = old_stderr
