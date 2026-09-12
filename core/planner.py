"""Domain and persistence logic for the planner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
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
		return asdict(self)


class PlannerStore:
	"""Load and save tasks in a small, forward-compatible JSON document."""

	def __init__(self, path: str | Path = "saves/plan.json") -> None:
		self.path = Path(path)

	def load(self) -> list[Task]:
		if not self.path.exists():
			return []

		try:
			with self.path.open("r", encoding="utf-8") as file:
				content = file.read()
			if not content.strip():
				return []
			document = json.loads(content)
		except json.JSONDecodeError as error:
			raise ValueError({error.msg}) from error

		raw_tasks = document.get("tasks") if isinstance(document, dict) else document
		if not isinstance(raw_tasks, list):
			raise ValueError("task 배열 필요")

		tasks = [self._task_from_dict(item) for item in raw_tasks]
		ids = [task.id for task in tasks]
		if len(ids) != len(set(ids)):
			raise ValueError("중복 task id")
		return tasks

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
				file.flush()
				os.fsync(file.fileno())
				temporary_path = Path(file.name)
			temporary_path.replace(self.path)
		finally:
			if temporary_path and temporary_path.exists():
				temporary_path.unlink()

	@staticmethod
	def _task_from_dict(item: Any) -> Task:
		if (
			not isinstance(item, dict)
			or not isinstance(item.get("id"), int)
			or isinstance(item.get("id"), bool)
			or item["id"] <= 0
		):
			raise ValueError("정수 id 필요")
		title = item.get("title")
		if not isinstance(title, str) or not title.strip():
			raise ValueError("title 문자열 없음")
		completed = item.get("completed", False)
		if not isinstance(completed, bool):
			raise ValueError("bool 형식 아님")
		created_at = item.get("created_at", "")
		if not isinstance(created_at, str):
			raise ValueError("created_at 문자열 아님")
		return Task(
			id=item["id"],
			title=title.strip(),
			completed=completed,
			created_at=created_at,
		)


class Planner:
	"""Use-case operations shared by CLI and future graphical interfaces."""

	def __init__(self, store: PlannerStore | None = None) -> None:
		self.store = store or PlannerStore()

	def list_tasks(self) -> list[Task]:
		return self.store.load()

	def add_task(self, title: str) -> Task:
		title = title.strip()
		if not title:
			raise ValueError("입력이란걸하셈")

		tasks = self.store.load()
		task = Task(
			id=max((item.id for item in tasks), default=0) + 1,
			title=title,
			created_at=datetime.now(timezone.utc).isoformat(),
		)
		tasks.append(task)
		self.store.save(tasks)
		return task

	def complete_task(self, task_id: int) -> Task:
		return self.set_completed(task_id, True)

	def set_completed(self, task_id: int, completed: bool) -> Task:
		tasks = self.store.load()
		task = self._find(tasks, task_id)
		task.completed = completed
		self.store.save(tasks)
		return task

	def remove_task(self, task_id: int) -> Task:
		tasks = self.store.load()
		task = self._find(tasks, task_id)
		tasks.remove(task)
		self.store.save(tasks)
		return task

	@staticmethod
	def _find(tasks: list[Task], task_id: int) -> Task:
		for task in tasks:
			if task.id == task_id:
				return task
		raise ValueError(f"{task_id} 없음")
