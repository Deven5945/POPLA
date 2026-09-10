"""Flet desktop UI for the planner and Pomodoro timer."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys

import flet as ft

from core.planner import Planner, Task
from core.pomodoro import Phase, PomodoroTimer, format_seconds


SOUND_PATH = Path(__file__).resolve().parent.parent / "sound" / "ring.mp3"


def play_ring(path: Path = SOUND_PATH) -> bool:
	"""Play the bundled alert sound without blocking the Flet event loop."""
	if not path.is_file():
		return False

	if os.name == "nt":
		command = ["cmd", "/c", "start", "", str(path)]
	elif sys.platform == "darwin":
		command = ["afplay", str(path)]
	else:
		player = next(
			(name for name in ("paplay", "mpg123", "ffplay") if shutil.which(name)),
			None,
		)
		if player is None:
			return False
		command = [player, "-nodisp", "-autoexit", str(path)] if player == "ffplay" else [player, str(path)]

	try:
		subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	except OSError:
		return False
	return True


class PlannerView:
	"""Desktop planner and Pomodoro workspace backed by shared domain services."""

	def __init__(self, page: ft.Page, planner: Planner) -> None:
		self.page = page
		self.planner = planner
		self.timer = PomodoroTimer()
		self.selected_task_id: int | None = None
		self.timer_task_active = False
		self.is_muted = False

		self.task_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
		self.summary = ft.Text(color=ft.Colors.BLUE_GREY_300)
		self.selected_task = ft.Text(
			"선택된 작업 없음",
			color=ft.Colors.BLUE_GREY_300,
			max_lines=1,
			overflow=ft.TextOverflow.ELLIPSIS,
		)
		self.title_input = ft.TextField(
			label="새 할 일",
			hint_text="예: 예시로 뭘 들지 생각하기",
			on_submit=self.add_task,
			expand=True,
		)
		self.phase_text = ft.Text(size=16, weight=ft.FontWeight.BOLD)
		self.timer_text = ft.Text(
			size=64,
			weight=ft.FontWeight.BOLD,
			color=ft.Colors.INDIGO_100,
		)
		self.progress = ft.ProgressBar(value=1, bar_height=8)
		self.cycle_text = ft.Text(color=ft.Colors.BLUE_GREY_300)
		self.start_button = ft.ElevatedButton(
			"시작",
			icon=ft.Icons.PLAY_ARROW,
			on_click=self.toggle_timer,
		)
		self.mute_button = ft.IconButton(
			icon=ft.Icons.VOLUME_UP,
			tooltip="알림음 음소거",
			on_click=self.toggle_mute,
		)

	def build(self) -> ft.Control:
		return ft.SafeArea(
			ft.Container(
				content=ft.Column(
					[
						self.build_header(),
						ft.ResponsiveRow(
							[
								ft.Column([self.build_planner_panel()], col={"sm": 12, "md": 7}),
								ft.Column([self.build_pomodoro_panel()], col={"sm": 12, "md": 5}),
							],
							expand=True,
						),
					],
					spacing=18,
					expand=True,
				),
				padding=ft.Padding(24, 20, 24, 20),
				expand=True,
			),
		)

	def build_header(self) -> ft.Control:
		return ft.ResponsiveRow(
			[
				ft.Column(
					[
						ft.Text("POPLA", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO_200),
						ft.Text("이것은제목이다", size=30, weight=ft.FontWeight.BOLD),
						ft.Text(
							"타이머 키고 딴짓하지 말자.",
							color=ft.Colors.BLUE_GREY_300,
						),
					],
					col={"sm": 12, "md": 8},
				),
				ft.Column([self.summary], col={"sm": 12, "md": 4}),
			]
		)

	def build_planner_panel(self) -> ft.Control:
		return ft.Container(
			content=ft.Column(
				[
					ft.Row(
						[
							ft.Text("플래너", size=20, weight=ft.FontWeight.BOLD),
							self.selected_task,
						],
						alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
					),
					ft.Row(
						[
							self.title_input,
							ft.IconButton(
								icon=ft.Icons.ADD,
								tooltip="할 일 추가",
								on_click=self.add_task,
							),
						]
					),
					ft.Divider(height=1),
					self.task_list,
				],
				spacing=14,
				expand=True,
			),
			padding=20,
			bgcolor=ft.Colors.BLUE_GREY_900,
			border_radius=8,
			expand=True,
		)

	def build_pomodoro_panel(self) -> ft.Control:
		return ft.Container(
			content=ft.Column(
				[
					ft.Text("포모도로", size=20, weight=ft.FontWeight.BOLD),
					self.phase_text,
					ft.Container(
						content=ft.Column(
							[
								self.timer_text,
								self.progress,
							],
							spacing=12,
						),
						padding=ft.Padding(0, 26, 0, 18),
					),
					self.cycle_text,
					ft.Row(
						[
							self.start_button,
							ft.IconButton(
								icon=ft.Icons.REFRESH,
								tooltip="타이머 초기화",
								on_click=self.reset_timer,
							),
							ft.IconButton(
								icon=ft.Icons.SKIP_NEXT,
								tooltip="단계 스킵",
								on_click=self.skip_phase,
							),
							self.mute_button,
						]
					),
				],
				spacing=14,
			),
			padding=20,
			bgcolor=ft.Colors.INDIGO_900,
			border_radius=8,
		)

	def refresh(self) -> None:
		self.refresh_tasks()
		self.refresh_timer()

	def refresh_tasks(self) -> None:
		tasks = self.planner.list_tasks()
		completed_count = sum(task.completed for task in tasks)
		self.summary.value = f"{completed_count}/{len(tasks)} 완료"
		selected = next((task for task in tasks if task.id == self.selected_task_id), None)
		self.selected_task.value = f"집중: {selected.title}" if selected else "선택된 작업 없음"
		self.task_list.controls = [self.task_row(task) for task in tasks]

	def refresh_timer(self) -> None:
		phase_names = {
			Phase.WORK: "집중 시간",
			Phase.SHORT_BREAK: "짧은 휴식",
			Phase.LONG_BREAK: "긴 휴식",
		}
		self.phase_text.value = phase_names[self.timer.phase]
		self.timer_text.value = format_seconds(self.timer.state.remaining_seconds)
		self.progress.value = self.timer.state.remaining_seconds / self.timer.total_seconds
		self.cycle_text.value = f"완료한 집중 세션 {self.timer.state.cycle}회"
		self.start_button.text = "일시정지" if self.timer.is_running else "시작"
		self.start_button.icon = ft.Icons.PAUSE if self.timer.is_running else ft.Icons.PLAY_ARROW

	def task_row(self, task: Task) -> ft.Control:
		text_style = (
			ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH, color=ft.Colors.BLUE_GREY_500)
			if task.completed
			else None
		)
		return ft.Container(
			content=ft.Row(
				[
					ft.Checkbox(value=task.completed, on_change=self.toggle_task, data=task.id),
					ft.Text(task.title, expand=True, selectable=True, style=text_style),
					ft.IconButton(
						icon=ft.Icons.TIMER_OUTLINED,
						tooltip="이 작업에 집중",
						data=task.id,
						on_click=self.select_task,
					),
					ft.IconButton(
						icon=ft.Icons.DELETE_OUTLINE,
						tooltip="할 일 삭제",
						data=task.id,
						on_click=self.delete_task,
					),
				],
				vertical_alignment=ft.CrossAxisAlignment.CENTER,
			),
			padding=ft.Padding(8, 4, 8, 4),
			border=ft.Border.all(1, ft.Colors.BLUE_GREY_700),
			border_radius=6,
		)

	def add_task(self, _: ft.ControlEvent | None = None) -> None:
		try:
			self.planner.add_task(self.title_input.value or "")
		except ValueError as error:
			self.notify(str(error))
			return
		self.title_input.value = ""
		self.refresh()
		self.page.update()

	def select_task(self, event: ft.ControlEvent) -> None:
		self.selected_task_id = int(event.control.data)
		self.refresh_tasks()
		self.page.update()

	def toggle_task(self, event: ft.ControlEvent) -> None:
		try:
			self.planner.set_completed(int(event.control.data), bool(event.control.value))
		except ValueError as error:
			self.notify(str(error))
			return
		self.refresh_tasks()
		self.page.update()

	def delete_task(self, event: ft.ControlEvent) -> None:
		task_id = int(event.control.data)
		try:
			self.planner.remove_task(task_id)
		except ValueError as error:
			self.notify(str(error))
			return
		if self.selected_task_id == task_id:
			self.selected_task_id = None
		self.refresh_tasks()
		self.page.update()

	def toggle_timer(self, _: ft.ControlEvent | None = None) -> None:
		if self.timer.is_running:
			self.timer.pause()
		else:
			self.timer.start()
			if not self.timer_task_active:
				self.timer_task_active = True
				self.page.run_task(self.timer_loop)
		self.refresh_timer()
		self.page.update()

	def reset_timer(self, _: ft.ControlEvent | None = None) -> None:
		self.timer.reset()
		self.refresh_timer()
		self.page.update()

	def skip_phase(self, _: ft.ControlEvent | None = None) -> None:
		self.timer.skip()
		if not self.is_muted:
			play_ring()
		self.refresh_timer()
		self.page.update()

	async def timer_loop(self) -> None:
		try:
			while self.timer.is_running:
				await asyncio.sleep(1)
				if not self.timer.is_running:
					break
				transitioned = self.timer.tick()
				self.refresh_timer()
				self.page.update()
				if transitioned:
					if not self.is_muted:
						play_ring()
					self.notify(f"{self.phase_text.value}이 시작되었습니다.")
		finally:
			self.timer_task_active = False

	def notify(self, message: str) -> None:
		self.page.snack_bar = ft.SnackBar(ft.Text(message))
		self.page.snack_bar.open = True
		self.page.update()

	def toggle_mute(self, _: ft.ControlEvent | None = None) -> None:
		self.is_muted = not self.is_muted
		self.mute_button.icon = ft.Icons.VOLUME_OFF if self.is_muted else ft.Icons.VOLUME_UP
		self.mute_button.tooltip = "알림음 켜기" if self.is_muted else "알림음 음소거"
		self.page.update()


def create_page(page: ft.Page, planner: Planner) -> None:
	"""Configure and mount the combined planner page for ``ft.app``."""
	page.title = "POPLA Focus Desk"
	page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
	page.theme_mode = ft.ThemeMode.DARK
	page.bgcolor = ft.Colors.BLUE_GREY_900
	page.padding = 0
	view = PlannerView(page, planner)
	page.add(view.build())
	view.refresh()
	page.update()


def run_app(planner: Planner) -> None:
	"""Start the cross-platform Flet desktop application."""
	ft.app(target=lambda page: create_page(page, planner))