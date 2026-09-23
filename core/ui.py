import asyncio
from datetime import datetime
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import flet as ft

from core.planner import Planner, Task
from core.pomodoro import Phase, PomodoroTimer, format_seconds


SOUND_PATH = Path(__file__).resolve().parent.parent / "sound" / "ring.mp3"


BACKGROUND = "#F5F8FC"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F8FAFD"
BORDER = "#E4EAF2"
TEXT = "#172033"
MUTED = "#728096"
PRIMARY = "#2563EB"
PRIMARY_DARK = "#1D4ED8"
PRIMARY_SOFT = "#EAF2FF"
SUCCESS = "#17835B"
FONT_FAMILY = "Noto Sans KR"


def play_ring(path: Path = SOUND_PATH) -> bool:
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
	def __init__(self, page: ft.Page, planner: Planner) -> None:
		self.page = page
		self.planner = planner
		self.timer = PomodoroTimer()
		self.selected_task_id: int | None = None
		self.task_filter = "all"
		self.timer_task_active = False
		self.last_timer_tick = 0.0
		self.is_muted = False

		self.task_list = ft.Column(spacing=10)
		self.selected_task = ft.Text(
			"선택된 작업 없음",
			color=MUTED,
			size=13,
			max_lines=1,
			overflow=ft.TextOverflow.ELLIPSIS,
			expand=True,
		)
		self.title_input = ft.TextField(
			label="새 작업",
			hint_text="할 일 입력하기",
			on_submit=self.add_task,
			expand=True,
			text_size=14,
			border=ft.InputBorder.OUTLINE,
			border_color=BORDER,
			focused_border_color=PRIMARY,
			bgcolor=SURFACE_ALT,
			border_radius=12,
			content_padding=ft.Padding(16, 14, 16, 14),
		)
		self.filter_buttons = {
			"all": ft.TextButton("전체", on_click=lambda _: self.set_filter("all")),
			"active": ft.TextButton("진행 중", on_click=lambda _: self.set_filter("active")),
			"completed": ft.TextButton("완료", on_click=lambda _: self.set_filter("completed")),
		}
		self.phase_text = ft.Text(size=13, weight=ft.FontWeight.BOLD, color=PRIMARY, no_wrap=True)
		self.phase_badge = ft.Container(
			content=self.phase_text,
			padding=ft.Padding(12, 7, 12, 7),
			bgcolor=PRIMARY_SOFT,
			border_radius=20,
		)
		self.timer_text = ft.Text(
			size=64,
			weight=ft.FontWeight.BOLD,
			color=TEXT,
			max_lines=1,
			no_wrap=True,
		)
		self.progress = ft.ProgressBar(value=1, bar_height=8, color=PRIMARY, bgcolor="#DCE7F8", expand=True)
		self.focus_target = ft.Text(
			"선택된 작업 없음",
			color=TEXT,
			size=14,
			weight=ft.FontWeight.BOLD,
			max_lines=1,
			overflow=ft.TextOverflow.ELLIPSIS,
		)
		self.start_button = ft.FilledButton(
			"시작",
			icon=ft.Icons.PLAY_ARROW,
			on_click=self.toggle_timer,
			style=ft.ButtonStyle(
				bgcolor=PRIMARY,
				color=ft.Colors.WHITE,
				padding=ft.Padding(22, 14, 22, 14),
				shape=ft.RoundedRectangleBorder(radius=10),
			),
		)
		self.mute_button = ft.IconButton(
			icon=ft.Icons.VOLUME_UP,
			tooltip="알림음 음소거",
			on_click=self.toggle_mute,
			style=ft.ButtonStyle(color=MUTED),
		)

	def build(self) -> ft.Control:
		return ft.SafeArea(
			ft.Container(
				content=ft.ListView(
					controls=[
						self.build_header(),
						ft.ResponsiveRow(
							[
								ft.Column([self.build_planner_panel()], col={"sm": 12, "lg": 8}),
								ft.Column([self.build_pomodoro_panel()], col={"sm": 12, "lg": 4}),
							],
							spacing=16,
							run_spacing=16,
						),
					],
					spacing=18,
					scroll=ft.ScrollMode.AUTO,
					padding=ft.Padding(24, 24, 24, 24),
					expand=True,
				),
				bgcolor=BACKGROUND,
				expand=True,
			),
		)

	def build_header(self) -> ft.Control:
		return ft.ResponsiveRow(
			[
				ft.Column(
					[
						ft.Row(
							[
								ft.Container(
									content=ft.Icon(ft.Icons.TASK_ALT, color=ft.Colors.WHITE, size=23),
									width=46,
									height=46,
									bgcolor=PRIMARY,
									border_radius=14,
									alignment=ft.Alignment.CENTER,
								),
								ft.Column(
									[
										ft.Text("POPLA", size=13, weight=ft.FontWeight.BOLD, color=PRIMARY),
										ft.Text("Focus Desk", size=22, weight=ft.FontWeight.BOLD, color=TEXT),
									],
									spacing=0,
								),
							],
							spacing=12,
						),
						ft.Text("할 건 제대로 해야지", color=MUTED, size=14),
					],
					col={"sm": 12, "md": 8},
				),
				ft.Column(
					[
						ft.Text(datetime.now().strftime("%Y년 %m월 %d일"), size=14, color=TEXT, weight=ft.FontWeight.BOLD),
						ft.Text("여기다뭐쓸지추천받음", size=12, color=MUTED),
					],
					col={"sm": 12, "md": 4},
					alignment=ft.MainAxisAlignment.CENTER,
				),
			],
			vertical_alignment=ft.CrossAxisAlignment.CENTER,
		)

	@staticmethod
	def card(content: ft.Control, padding: int = 24, bgcolor: str = SURFACE) -> ft.Control:
		return ft.Container(
			content=content,
			padding=ft.Padding(padding, padding, padding, padding),
			bgcolor=bgcolor,
			border=ft.Border.all(1, BORDER),
			border_radius=18,
		)

	def build_planner_panel(self) -> ft.Control:
		return self.card(
			ft.Column(
				[
					ft.Row(
						[
							ft.Column(
								[
									ft.Text("플래너", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
									ft.Text("할 일 목록", size=13, color=MUTED),
								],
								spacing=3,
								expand=True,
							),
						],
						alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
					),
					ft.Row(
						[
							self.title_input,
							ft.FilledButton(
								"추가",
								icon=ft.Icons.ADD,
								on_click=self.add_task,
								style=ft.ButtonStyle(
									bgcolor=PRIMARY,
									color=ft.Colors.WHITE,
									padding=ft.Padding(18, 15, 18, 15),
									shape=ft.RoundedRectangleBorder(radius=10),
								),
							),
						],
						vertical_alignment=ft.CrossAxisAlignment.CENTER,
					),
					ft.Container(
						content=ft.Row(list(self.filter_buttons.values()), spacing=2),
						padding=ft.Padding(4, 2, 4, 2),
						bgcolor=SURFACE_ALT,
						border_radius=10,
					),
					ft.Container(
						content=ft.Row(
							[
								ft.Icon(ft.Icons.ADS_CLICK, size=16, color=PRIMARY),
								self.selected_task,
							],
							spacing=8,
						),
						padding=ft.Padding(12, 10, 12, 10),
						bgcolor=PRIMARY_SOFT,
						border_radius=10,
					),
					self.task_list,
				],
				spacing=16,
			),
		)

	def build_pomodoro_panel(self) -> ft.Control:
		return self.card(
			ft.Column(
				[
					ft.Row(
						[
							ft.Column(
								[
									ft.Text("포모도로", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
									ft.Text("집중 타이머", size=13, color=MUTED),
								],
								spacing=3,
								expand=True,
							),
							self.phase_badge,
						],
						alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
					),
					ft.Container(
						content=ft.Column(
							[
								self.timer_text,
								self.progress,
							],
							spacing=14,
							horizontal_alignment=ft.CrossAxisAlignment.CENTER,
						),
						padding=ft.Padding(0, 38, 0, 26),
					),
					ft.Container(
						content=ft.Row(
							[
								ft.Container(
									content=ft.Icon(ft.Icons.TASK_ALT, color=PRIMARY, size=18),
									width=34,
									height=34,
									bgcolor=SURFACE,
									border_radius=10,
									alignment=ft.Alignment.CENTER,
								),
								ft.Column(
									[
										ft.Text("집중 중:", size=11, color=MUTED),
										self.focus_target,
									],
									spacing=2,
									expand=True,
								),
							],
							spacing=10,
						),
						padding=ft.Padding(12, 10, 12, 10),
						bgcolor=PRIMARY_SOFT,
						border_radius=12,
					),
					ft.Row(
						[
							self.start_button,
							ft.IconButton(
								icon=ft.Icons.REFRESH,
								tooltip="타이머 초기화",
								on_click=self.reset_timer,
								style=ft.ButtonStyle(color=MUTED),
							),
							ft.IconButton(
								icon=ft.Icons.SKIP_NEXT,
								tooltip="단계 스킵",
								on_click=self.skip_phase,
								style=ft.ButtonStyle(color=MUTED),
							),
							self.mute_button,
						],
						spacing=2,
						wrap=True,
						run_spacing=4,
					),
				],
				spacing=18,
			),
			bgcolor="#F0F5FF",
		)

	def refresh(self) -> None:
		self.refresh_tasks()
		self.refresh_timer()

	def refresh_tasks(self) -> None:
		tasks = self.planner.list_tasks()
		selected = next((task for task in tasks if task.id == self.selected_task_id), None)
		self.selected_task.value = f"집중 중: {selected.title}" if selected else "집중 항목 없음"
		self.focus_target.value = selected.title if selected else "선택된 작업 없음"

		if self.task_filter == "active":
			visible_tasks = [task for task in tasks if not task.completed]
		elif self.task_filter == "completed":
			visible_tasks = [task for task in tasks if task.completed]
		else:
			visible_tasks = tasks
		self.task_list.controls = (
			[self.task_row(task) for task in visible_tasks]
			if visible_tasks
			else [self.empty_task_state()]
		)
		self.update_filter_buttons()

	def refresh_timer(self) -> None:
		phase_names = {
			Phase.WORK: "집중 시간",
			Phase.SHORT_BREAK: "짧은 휴식",
			Phase.LONG_BREAK: "긴 휴식",
		}
		self.phase_text.value = phase_names[self.timer.phase]
		self.timer_text.value = format_seconds(self.timer.state.remaining_seconds)
		self.progress.value = max(0, min(1, self.timer.state.remaining_seconds / self.timer.total_seconds))
		self.start_button.text = "일시정지" if self.timer.is_running else "시작"
		self.start_button.icon = ft.Icons.PAUSE if self.timer.is_running else ft.Icons.PLAY_ARROW
		self.start_button.style = ft.ButtonStyle(
			bgcolor=PRIMARY_DARK if self.timer.is_running else PRIMARY,
			color=ft.Colors.WHITE,
			padding=ft.Padding(22, 14, 22, 14),
			shape=ft.RoundedRectangleBorder(radius=10),
		)

	def set_filter(self, task_filter: str) -> None:
		self.task_filter = task_filter
		self.refresh_tasks()
		self.page.update()

	def update_filter_buttons(self) -> None:
		for name, button in self.filter_buttons.items():
			button.style = ft.ButtonStyle(
				color=PRIMARY if name == self.task_filter else MUTED,
				bgcolor=PRIMARY_SOFT if name == self.task_filter else SURFACE_ALT,
				shape=ft.RoundedRectangleBorder(radius=8),
			)

	@staticmethod
	def empty_task_state() -> ft.Control:
		return ft.Container(
			content=ft.Column(
				[
					ft.Icon(ft.Icons.INBOX_OUTLINED, size=32, color="#9AA8BB"),
					ft.Text("표시할 작업이 없음", color=TEXT, weight=ft.FontWeight.BOLD),
					ft.Text("새 작업을 추가해 시작하기", color=MUTED, size=12),
				],
				spacing=7,
				horizontal_alignment=ft.CrossAxisAlignment.CENTER,
			),
			padding=ft.Padding(20, 34, 20, 34),
			bgcolor=SURFACE_ALT,
			border_radius=12,
		)

	def task_row(self, task: Task) -> ft.Control:
		text_style = (
			ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH, color="#9AA8BB")
			if task.completed
			else ft.TextStyle(color=TEXT)
		)
		is_selected = task.id == self.selected_task_id
		return ft.Container(
			content=ft.Row(
				[
					ft.Checkbox(
						value=task.completed,
						on_change=self.toggle_task,
						data=task.id,
						fill_color="#B9CBEA",
						check_color=PRIMARY,
						overlay_color="#E7EEF9",
					),
					ft.Column(
						[
							ft.Text(task.title, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, selectable=True, style=text_style),
							ft.Text("완료됨" if task.completed else "진행 중", size=11, color=SUCCESS if task.completed else MUTED),
						],
						spacing=2,
						expand=True,
					),
					ft.IconButton(
						icon=ft.Icons.TIMER_OUTLINED,
						tooltip="이 작업에 집중",
						data=task.id,
						on_click=self.select_task,
						style=ft.ButtonStyle(color=PRIMARY if is_selected else MUTED),
					),
					ft.IconButton(
						icon=ft.Icons.DELETE_OUTLINE,
						tooltip="삭제",
						data=task.id,
						on_click=self.delete_task,
						style=ft.ButtonStyle(color=MUTED),
					),
				],
				vertical_alignment=ft.CrossAxisAlignment.CENTER,
			),
			padding=ft.Padding(8, 4, 8, 4),
			bgcolor=PRIMARY_SOFT if is_selected else SURFACE,
			border=ft.Border.all(1, PRIMARY if is_selected else BORDER),
			border_radius=12,
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
			self.last_timer_tick = time.monotonic()
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
		last_display_seconds: int | None = None
		last_display_phase: Phase | None = None
		try:
			while self.timer.is_running:
				await asyncio.sleep(0.25)
				if not self.timer.is_running:
					break
				now = time.monotonic()
				elapsed = max(0.0, now - self.last_timer_tick)
				self.last_timer_tick = now
				transitioned = self.timer.tick(elapsed)
				display_seconds = math.ceil(self.timer.state.remaining_seconds)
				should_update = (
					display_seconds != last_display_seconds
					or self.timer.phase != last_display_phase
					or transitioned
				)
				if should_update:
					self.refresh_timer()
					self.page.update()
					last_display_seconds = display_seconds
					last_display_phase = self.timer.phase
				if transitioned:
					if not self.is_muted:
						play_ring()
					self.notify(f"{self.phase_text.value}이 시작되었습니다")
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
	page.theme = ft.Theme(color_scheme_seed=PRIMARY, font_family=FONT_FAMILY)
	page.theme_mode = ft.ThemeMode.LIGHT
	page.bgcolor = BACKGROUND
	page.padding = 0
	view = PlannerView(page, planner)
	page.add(view.build())
	view.refresh()
	page.update()


def run_app(planner: Planner) -> None:
	"""Start the cross-platform Flet desktop application."""
	ft.app(target=lambda page: create_page(page, planner))
