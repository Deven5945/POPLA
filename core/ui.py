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


BACKGROUND = "#080B14"
SURFACE = "#101624"
SURFACE_ALT = "#171F31"
SURFACE_RAISED = "#1D2840"
BORDER = "#26334D"
TEXT = "#F4F7FC"
MUTED = "#8D9AB2"
PRIMARY = "#8B6CFF"
PRIMARY_DARK = "#6F50E8"
PRIMARY_SOFT = "#241C4B"
MINT = "#35D6A1"
MINT_SOFT = "#123C37"
SKY = "#50B8FF"
SKY_SOFT = "#12324B"
DANGER = "#FF6F86"
FONT_FAMILY = "Noto Sans KR"


PHASE_META = {
	Phase.WORK: {
		"label": "집중",
		"icon": ft.Icons.BOLT,
		"color": PRIMARY,
		"soft": PRIMARY_SOFT,
	},
	Phase.SHORT_BREAK: {
		"label": "짧은 휴식",
		"icon": ft.Icons.COFFEE_OUTLINED,
		"color": MINT,
		"soft": MINT_SOFT,
	},
	Phase.LONG_BREAK: {
		"label": "긴 휴식",
		"icon": ft.Icons.NIGHTLIGHT_OUTLINED,
		"color": SKY,
		"soft": SKY_SOFT,
	},
}


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

		self.task_list = ft.Column(spacing=8)
		self.task_count = ft.Text("0", size=12, color=MUTED, weight=ft.FontWeight.BOLD)
		self.selected_task = ft.Text(
			"선택 없음",
			color=MUTED,
			size=13,
			max_lines=1,
			overflow=ft.TextOverflow.ELLIPSIS,
			expand=True,
		)
		self.title_input = ft.TextField(
			hint_text="새 작업",
			prefix_icon=ft.Icons.ADD_TASK_OUTLINED,
			on_submit=self.add_task,
			expand=True,
			text_size=14,
			color=TEXT,
			cursor_color=PRIMARY,
			border=ft.InputBorder.OUTLINE,
			border_color=BORDER,
			focused_border_color=PRIMARY,
			bgcolor=SURFACE_ALT,
			border_radius=12,
			content_padding=ft.Padding(16, 14, 16, 14),
		)
		self.filter_buttons = {
			"all": ft.IconButton(
				icon=ft.Icons.LIST_ALT_OUTLINED,
				tooltip="전체 작업",
				on_click=lambda _: self.set_filter("all"),
			),
			"active": ft.IconButton(
				icon=ft.Icons.RADIO_BUTTON_CHECKED,
				tooltip="진행 중",
				on_click=lambda _: self.set_filter("active"),
			),
			"completed": ft.IconButton(
				icon=ft.Icons.TASK_ALT,
				tooltip="완료",
				on_click=lambda _: self.set_filter("completed"),
			),
		}
		self.phase_icon = ft.Icon(ft.Icons.TIMER_OUTLINED, size=16)
		self.phase_text = ft.Text(size=12, weight=ft.FontWeight.BOLD, no_wrap=True)
		self.phase_badge = ft.Container(
			content=ft.Row([self.phase_icon, self.phase_text], spacing=5),
			padding=ft.Padding(10, 6, 10, 6),
			bgcolor=PRIMARY_SOFT,
			border_radius=20,
		)
		self.timer_text = ft.Text(
			size=112,
			weight=ft.FontWeight.BOLD,
			color=TEXT,
			max_lines=1,
			no_wrap=True,
			text_align=ft.TextAlign.CENTER,
		)
		self.progress = ft.ProgressBar(value=1, bar_height=7, bgcolor=BORDER, expand=True)
		self.focus_target = ft.Text(
			"선택 없음",
			color=TEXT,
			size=14,
			weight=ft.FontWeight.BOLD,
			max_lines=1,
			overflow=ft.TextOverflow.ELLIPSIS,
		)
		self.start_button = ft.IconButton(
			icon=ft.Icons.PLAY_ARROW,
			tooltip="타이머 시작",
			icon_size=28,
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
								ft.Column([self.build_timer_panel()], col={"sm": 12, "lg": 7}),
								ft.Column([self.build_planner_panel()], col={"sm": 12, "lg": 5}),
							],
							spacing=18,
							run_spacing=18,
						),
					],
					spacing=18,
					expand=True,
				),
				bgcolor=BACKGROUND,
				padding=ft.Padding(22, 20, 22, 22),
				expand=True,
			),
		)

	def build_header(self) -> ft.Control:
		return ft.Row(
			[
				ft.Row(
					[
						ft.Container(
							content=ft.Icon(ft.Icons.TIMER_OUTLINED, color=BACKGROUND, size=21),
							width=42,
							height=42,
							bgcolor=PRIMARY,
							border_radius=13,
							alignment=ft.Alignment.CENTER,
						),
						ft.Text("POPLA", size=19, weight=ft.FontWeight.BOLD, color=TEXT),
					],
					spacing=10,
				),
				ft.Row(
					[
					ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, size=16, color=MUTED),
					ft.Text(datetime.now().strftime("%m.%d"), size=13, color=MUTED, weight=ft.FontWeight.BOLD),
					],
					spacing=6,
				),
			],
			alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
		)

	@staticmethod
	def card(content: ft.Control, padding: int = 20, bgcolor: str = SURFACE) -> ft.Control:
		return ft.Container(
			content=content,
			padding=ft.Padding(padding, padding, padding, padding),
			bgcolor=bgcolor,
			border=ft.Border.all(1, BORDER),
			border_radius=24,
		)

	@staticmethod
	def icon_button_style(color: str = MUTED, bgcolor: str = "transparent", radius: int = 11) -> ft.ButtonStyle:
		return ft.ButtonStyle(
			color=color,
			bgcolor=bgcolor,
			padding=ft.Padding(10, 10, 10, 10),
			shape=ft.RoundedRectangleBorder(radius=radius),
		)

	def build_timer_panel(self) -> ft.Control:
		return self.card(
			ft.Column(
				[
					ft.Row(
						[
							ft.Row(
								[
									ft.Icon(ft.Icons.TIMER_OUTLINED, color=TEXT, size=21),
									ft.Text("타이머", size=17, weight=ft.FontWeight.BOLD, color=TEXT),
								],
								spacing=8,
							),
							self.phase_badge,
						],
						alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
					),
					ft.Container(
						content=ft.Column(
							[
								ft.Row(
									[self.timer_text],
									alignment=ft.MainAxisAlignment.CENTER,
									expand=True,
								),
								ft.Row(
									[ft.Container(content=self.progress, width=320)],
									alignment=ft.MainAxisAlignment.CENTER,
									expand=True,
								),
							],
							spacing=18,
							horizontal_alignment=ft.CrossAxisAlignment.CENTER,
						),
						padding=ft.Padding(0, 58, 0, 48),
						alignment=ft.Alignment.CENTER,
						expand=True,
					),
					ft.Container(
						content=ft.Row(
							[
								ft.Container(
									content=ft.Icon(ft.Icons.TASK_ALT, color=PRIMARY, size=18),
									width=34,
									height=34,
									bgcolor=PRIMARY_SOFT,
									border_radius=10,
									alignment=ft.Alignment.CENTER,
								),
								self.focus_target,
							],
							spacing=10,
						),
						padding=ft.Padding(12, 10, 12, 10),
						bgcolor=SURFACE_ALT,
						border_radius=13,
					),
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
						],
						alignment=ft.MainAxisAlignment.CENTER,
						spacing=8,
					),
				],
				spacing=18,
			),
			bgcolor="#11192B",
		)

	def build_planner_panel(self) -> ft.Control:
		return self.card(
			ft.Column(
				[
					ft.Row(
						[
							ft.Row(
								[
									ft.Icon(ft.Icons.CHECKLIST_OUTLINED, color=MINT, size=20),
									ft.Text("작업", size=17, weight=ft.FontWeight.BOLD, color=TEXT),
									self.task_count,
								],
								spacing=8,
							),
							ft.Container(
								content=ft.Row(list(self.filter_buttons.values()), spacing=0),
								padding=ft.Padding(2, 2, 2, 2),
								bgcolor=SURFACE_ALT,
								border_radius=11,
							),
						],
						alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
						vertical_alignment=ft.CrossAxisAlignment.CENTER,
					),
					ft.Row(
						[
							self.title_input,
							ft.IconButton(
								icon=ft.Icons.ADD,
								icon_size=22,
								tooltip="작업 추가",
								on_click=self.add_task,
								style=self.icon_button_style(TEXT, PRIMARY, 12),
							),
						],
						vertical_alignment=ft.CrossAxisAlignment.CENTER,
					),
					ft.Container(
						content=ft.Row(
							[
								ft.Icon(ft.Icons.ADS_CLICK, size=16, color=PRIMARY),
								self.selected_task,
							],
							spacing=8,
						),
						padding=ft.Padding(11, 9, 11, 9),
						bgcolor=PRIMARY_SOFT,
						border_radius=11,
					),
					self.task_list,
				],
				spacing=14,
			),
			bgcolor=SURFACE,
		)

	def refresh(self) -> None:
		self.refresh_tasks()
		self.refresh_timer()

	def refresh_tasks(self) -> None:
		tasks = self.planner.list_tasks()
		selected = next((task for task in tasks if task.id == self.selected_task_id), None)
		self.selected_task.value = selected.title if selected else "선택 없음"
		self.focus_target.value = selected.title if selected else "선택 없음"
		self.task_count.value = str(len(tasks))

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
		meta = PHASE_META[self.timer.phase]
		self.phase_icon.name = meta["icon"]
		self.phase_icon.color = meta["color"]
		self.phase_text.value = meta["label"]
		self.phase_text.color = meta["color"]
		self.phase_badge.bgcolor = meta["soft"]
		self.timer_text.value = format_seconds(self.timer.state.remaining_seconds)
		self.progress.value = max(0, min(1, self.timer.state.remaining_seconds / self.timer.total_seconds))
		self.progress.color = meta["color"]
		self.start_button.icon = ft.Icons.PAUSE if self.timer.is_running else ft.Icons.PLAY_ARROW
		self.start_button.tooltip = "타이머 일시정지" if self.timer.is_running else "타이머 시작"
		self.start_button.style = ft.ButtonStyle(
			bgcolor=PRIMARY_DARK if self.timer.is_running else meta["color"],
			color=BACKGROUND,
			padding=ft.Padding(16, 16, 16, 16),
			shape=ft.RoundedRectangleBorder(radius=18),
		)
		self.mute_button.style = self.icon_button_style(MUTED, SURFACE_RAISED)

	def set_filter(self, task_filter: str) -> None:
		self.task_filter = task_filter
		self.refresh_tasks()
		self.page.update()

	def update_filter_buttons(self) -> None:
		for name, button in self.filter_buttons.items():
			button.style = self.icon_button_style(
				color=TEXT if name == self.task_filter else MUTED,
				bgcolor=PRIMARY_SOFT if name == self.task_filter else "transparent",
				radius=9,
			)

	@staticmethod
	def empty_task_state() -> ft.Control:
		return ft.Container(
			content=ft.Column(
				[
					ft.Icon(ft.Icons.INBOX_OUTLINED, size=30, color=MUTED),
					ft.Text("작업 없음", color=MUTED, size=13),
				],
				spacing=8,
				horizontal_alignment=ft.CrossAxisAlignment.CENTER,
			),
			padding=ft.Padding(18, 28, 18, 28),
			bgcolor=SURFACE_ALT,
			border_radius=12,
		)

	@staticmethod
	def format_created_at(created_at: str) -> str:
		if not created_at:
			return ""
		try:
			created = datetime.fromisoformat(created_at)
		except ValueError:
			return ""
		return created.strftime("%m월 %d일 %H:%M")

	def task_row(self, task: Task) -> ft.Control:
		text_style = (
			ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH, color="#68748A")
			if task.completed
			else ft.TextStyle(color=TEXT)
		)
		is_selected = task.id == self.selected_task_id
		created_label = self.format_created_at(task.created_at)
		task_details = [
			ft.Text(task.title, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, selectable=True, style=text_style)
		]
		if created_label:
			task_details.append(ft.Text(created_label, size=10, height=14, color=MUTED, max_lines=1, no_wrap=True))
		task_info = ft.Column(
			task_details,
			spacing=0,
			tight=True,
			horizontal_alignment=ft.CrossAxisAlignment.START,
		)
		return ft.Container(
			content=ft.Row(
				[
					ft.Checkbox(
						value=task.completed,
						on_change=self.toggle_task,
						data=task.id,
						fill_color=SURFACE_RAISED,
						check_color=MINT,
						overlay_color=MINT_SOFT,
					),
					task_info,
					ft.Container(expand=True),
					ft.IconButton(
						icon=ft.Icons.TIMER_OUTLINED,
						tooltip="이 작업에 집중",
						data=task.id,
						on_click=self.select_task,
						style=self.icon_button_style(PRIMARY if is_selected else MUTED),
					),
					ft.IconButton(
						icon=ft.Icons.DELETE_OUTLINE,
						tooltip="삭제",
						data=task.id,
						on_click=self.delete_task,
						style=self.icon_button_style(DANGER),
					),
				],
				vertical_alignment=ft.CrossAxisAlignment.CENTER,
				intrinsic_height=True,
				spacing=2,
			),
			height=64,
			padding=ft.Padding(5, 6, 5, 6),
			bgcolor=PRIMARY_SOFT if is_selected else SURFACE_ALT,
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
	"""Configure and mount the dark timer-first planner page."""
	page.title = "POPLA"
	page.theme = ft.Theme(color_scheme_seed=PRIMARY, font_family=FONT_FAMILY)
	page.theme_mode = ft.ThemeMode.DARK
	page.bgcolor = BACKGROUND
	page.padding = 0
	view = PlannerView(page, planner)
	page.add(view.build())
	view.refresh()
	page.update()


def run_app(planner: Planner) -> None:
	"""Start the cross-platform Flet desktop application."""
	ft.app(target=lambda page: create_page(page, planner))
