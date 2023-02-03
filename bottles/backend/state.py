import dataclasses
from enum import Enum
from gettext import gettext as _
from threading import Lock as PyLock, Event as PyEvent
from typing import Dict, Callable, Optional, Union, Protocol, List
from uuid import UUID, uuid4

from bottles.backend.logger import Logger
from bottles.backend.models.result import Result

logging = Logger()


class Locks(Enum):
    ComponentsInstall = "components.install"


class Events(Enum):
    pass


class Signals(Enum):
    """Signals backend support"""
    ManagerLocalBottlesLoaded = "Manager.local_bottles_loaded"  # no extra data

    RepositoryFetched = "RepositoryManager.repo_fetched"  # status: fetch success or not, data(int): total repositories
    NetworkStatusChanged = "ConnectionUtils.status_changed"  # status(bool): network ready or not

    GNotification = "G.send_notification"  # data(Notification): data for Gio notification
    GShowUri = "G.show_uri"  # data(str): the URI

    # data(UUID): the UUID of task
    TaskAdded = "task.added"
    TaskRemoved = "task.removed"
    TaskUpdated = "task.updated"


class Status(Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskStreamUpdateHandler(Protocol):
    def __call__(self, received_size: int = 0, total_size: int = 0, status: Status = None) -> None: ...


class SignalHandler(Protocol):
    def __call__(self, data: Optional[Result] = None) -> None: ...


@dataclasses.dataclass
class Notification:
    title: str = "Bottles"
    text: str = "no message provided"
    image: str = ""


@dataclasses.dataclass(init=False)
class Task:
    _task_id: Optional[UUID] = None  # should only be set by TaskManager
    title: str = "Task"
    _subtitle: str = ""
    hidden: bool = False  # hide from UI
    cancellable: bool = False

    def __init__(self, title: str = "Task", subtitle: str = "", hidden: bool = False, cancellable: bool = False):
        self.title = title
        self.subtitle = subtitle
        self.hidden = hidden
        self.cancellable = cancellable

    @property
    def task_id(self) -> UUID:
        return self._task_id

    @task_id.setter
    def task_id(self, value: UUID):
        if self._task_id is not None:
            raise NotImplementedError("Invalid usage, Task.task_id should only set once")
        self._task_id = value

    @property
    def subtitle(self) -> str:
        return self._subtitle

    @subtitle.setter
    def subtitle(self, value: str):
        self._subtitle = value
        State.send_signal(Signals.TaskUpdated, Result(True, self.task_id))

    def stream_update(self, received_size: int = 0, total_size: int = 0, status: Status = None):
        """This is a default subtitle updating handler for streaming downloading progress"""
        match status:
            case Status.DONE, Status.FAILED:
                TaskManager.remove_task(self)
                return
            case _:
                pass

        if total_size == 0 and received_size == 0:
            self.subtitle = _("Calculating…")
            return

        percent = int(received_size / total_size * 100)
        self.subtitle = f"{percent}%"


class LockManager:
    _LOCKS: Dict[Locks, PyLock] = {}

    @classmethod
    def lock(cls, name: Locks):
        """decorator, used for mutex locking the decorated function"""
        lock = cls.get_lock(name)

        def func_wrapper(func: Callable):
            def wrapper(*args, **kwargs):
                lock.acquire()
                rv = func(*args, **kwargs)
                lock.release()
                return rv

            return wrapper

        return func_wrapper

    @classmethod
    def get_lock(cls, name: Locks) -> PyLock:
        return cls._LOCKS.setdefault(name, PyLock())


class EventManager:
    _EVENTS: Dict[Events, PyEvent] = {}


class TaskManager:
    """Long-running tasks are registered here, for tracking and display them on UI"""
    _TASKS: Dict[UUID, Task] = {}  # {UUID4: Task}

    @classmethod
    def get_task(cls, task_id: UUID) -> Optional[Task]:
        return cls._TASKS.get(task_id)

    @classmethod
    def add_task(cls, task: Task) -> UUID:
        """register a running task to TaskManager"""
        uniq = uuid4()
        task.task_id = uniq
        cls._TASKS[uniq] = task
        State.send_signal(Signals.TaskAdded, Result(True, task.task_id))
        return uniq

    @classmethod
    def remove_task(cls, task: Union[UUID, Task]):
        if isinstance(task, Task):
            task = task.task_id
        cls._TASKS.pop(task)
        State.send_signal(Signals.TaskRemoved, Result(True, task))


class SignalManager:
    """sync backend state to frontend via registered signal handlers"""
    _SIGNALS: Dict[Signals, List[SignalHandler]] = {}

    @classmethod
    def connect_signal(cls, signal: Signals, handler: SignalHandler) -> None:
        cls._SIGNALS.setdefault(signal, [])
        cls._SIGNALS[signal].append(handler)

    @classmethod
    def send_signal(cls, signal: Signals, data: Optional[Result] = None) -> None:
        """
        Send signal
        should only be called by backend logic
        """
        if signal not in cls._SIGNALS:
            logging.debug(f"No handler registered for {signal}")
            return
        for fn in cls._SIGNALS[signal]:
            fn(data)


class State(LockManager, EventManager, TaskManager, SignalManager):
    """Unified State Management"""
    pass
