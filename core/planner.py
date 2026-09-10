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
			raise ValueError(f"plan.json의 JSON 형식이 올바르지 않습니다: {error.msg}") from error

		raw_tasks = document.get("tasks") if isinstance(document, dict) else document
		if not isinstance(raw_tasks, list):
			raise ValueError("plan.json은 tasks 배열을 포함해야 합니다.")

		tasks = [self._task_from_dict(item) for item in raw_tasks]
		ids = [task.id for task in tasks]
		if len(ids) != len(set(ids)):
			raise ValueError("plan.json에는 중복된 task id가 있습니다.")
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
			raise ValueError("각 task에는 정수 id가 필요합니다.")
		title = item.get("title")
		if not isinstance(title, str) or not title.strip():
			raise ValueError("각 task에는 비어 있지 않은 title이 필요합니다.")
		completed = item.get("completed", False)
		if not isinstance(completed, bool):
			raise ValueError("task의 completed 값은 boolean이어야 합니다.")
		created_at = item.get("created_at", "")
		if not isinstance(created_at, str):
			raise ValueError("task의 created_at 값은 문자열이어야 합니다.")
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
			raise ValueError("할 일 내용을 입력해야 합니다.")

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
		raise ValueError(f"task {task_id}를 찾을 수 없습니다.")
