"""Domain and persistence logic for the planner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any


@dataclass
class Task:
	"""A planner item kept independent from any user interface."""

	id: int
	title: str
	completed: bool = False
	created_at: str = ""

	def to_dict(self) -> dict[str, Any]:
		return {
			"id": self.id,
			"title": self.title,
			"completed": self.completed,
			"created_at": self.created_at,
		}


class PlannerStore:
	"""Load and save tasks in a small, forward-compatible JSON document."""

	def __init__(self, path: str | Path = "saves/plan.json") -> None:
		self.path = Path(path)

	def load(self) -> list[Task]:
		try:
			with self.path.open("r", encoding="utf-8") as file:
				content = file.read()
		except FileNotFoundError:
			return []
		if not content.strip():
			return []

		document = json.loads(content)

		raw_tasks = document.get("tasks", document) if isinstance(document, dict) else document
		if not isinstance(raw_tasks, list):
			raise ValueError("plan.json은 tasks 배열을 포함해야 합니다.")

		return [self._task_from_dict(item) for item in raw_tasks]

	def save(self, tasks: list[Task]) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		document = {"version": 1, "tasks": [task.to_dict() for task in tasks]}
		temporary_path: Path | None = None

		try:
			with tempfile.NamedTemporaryFile(
				mode="w",
				encoding="utf-8",
				dir=self.path.parent,
				prefix=f".{self.path.name}.",
				delete=False,
			) as file:
				json.dump(document, file, ensure_ascii=False, indent=2)
				file.write("\n")
				temporary_path = Path(file.name)
			temporary_path.replace(self.path)
		finally:
			if temporary_path and temporary_path.exists():
				temporary_path.unlink()

	@staticmethod
	def _task_from_dict(item: Any) -> Task:
		if not isinstance(item, dict) or not isinstance(item.get("id"), int):
			raise ValueError("각 task에는 정수 id가 필요합니다.")
		title = item.get("title")
		if not isinstance(title, str) or not title.strip():
			raise ValueError("각 task에는 비어 있지 않은 title이 필요합니다.")
		return Task(
			id=item["id"],
			title=title,
			completed=bool(item.get("completed", False)),
			created_at=str(item.get("created_at", "")),
		)


class Planner:
	"""Use-case operations shared by CLI and future graphical interfaces."""

	def __init__(self, store: PlannerStore | None = None) -> None:
		self.store = store or PlannerStore()
		self._tasks: list[Task] | None = None
		self._next_task_id: int | None = None

	def _load_tasks(self) -> list[Task]:
		"""Load once per planner instance and keep subsequent UI reads in memory."""
		if self._tasks is None:
			self._tasks = self.store.load()
			self._next_task_id = max((item.id for item in self._tasks), default=0) + 1
		return self._tasks

	def list_tasks(self) -> list[Task]:
		return list(self._load_tasks())

	def add_task(self, title: str) -> Task:
		title = title.strip()
		if not title:
			raise ValueError("할 일 내용을 입력해야 합니다.")

		tasks = self._load_tasks()
		task = Task(
			id=self._next_task_id or 1,
			title=title,
			created_at=datetime.now(timezone.utc).isoformat(),
		)
		tasks.append(task)
		self._next_task_id = task.id + 1
		self.store.save(tasks)
		return task

	def complete_task(self, task_id: int) -> Task:
		return self.set_completed(task_id, True)

	def set_completed(self, task_id: int, completed: bool) -> Task:
		tasks = self._load_tasks()
		task = self._find(tasks, task_id)
		if task.completed == completed:
			return task
		task.completed = completed
		self.store.save(tasks)
		return task

	def remove_task(self, task_id: int) -> Task:
		tasks = self._load_tasks()
		task = self._find(tasks, task_id)
		tasks.remove(task)
		self.store.save(tasks)
		return task

	@staticmethod
	def _find(tasks: list[Task], task_id: int) -> Task:
		for task in tasks:
			if task.id == task_id:
				return task
		raise ValueError(f"task {task_id}를 찾을 수 없습니다.")
