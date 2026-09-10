"""Flet desktop UI for the planner and Pomodoro timer."""

from __future__ import annotations

import asyncio
from math import ceil
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import flet as ft
try:
	import pygame
except ImportError:
	pygame = None

from core.planner import Planner, Task
from core.pomodoro import Phase, PomodoroTimer, format_seconds


SOUND_PATH = Path(__file__).resolve().parent.parent / "sound" / "ring.mp3"
TIMER_POLL_INTERVAL = 0.25
PAGE_BG = "#0F131A"
SURFACE = "#171D27"
SURFACE_ELEVATED = "#1D2633"
BORDER = "#2A3444"
TEXT_PRIMARY = "#F4F6FA"
TEXT_MUTED = "#98A2B3"
ACCENT = "#A9B5FF"
ACCENT_STRONG = "#7E8DFF"
ACCENT_SOFT = "#28304D"
PHASE_NAMES = {
	Phase.WORK: "집중 시간",
	Phase.SHORT_BREAK: "짧은 휴식",
	Phase.LONG_BREAK: "긴 휴식",
}


def play_ring_native(path: Path = SOUND_PATH) -> bool:
	"""Fallback player for systems where pygame audio is unavailable."""
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


class SoundPlayer:
	"""Preload the alert sound and keep native playback as a fallback."""

	def __init__(self, path: Path = SOUND_PATH) -> None:
		self.path = path
		self.sound = None
		self._ready = False
		if pygame is not None and path.is_file():
			try:
				pygame.mixer.init()
				self.sound = pygame.mixer.Sound(str(path))
				self._ready = True
			except pygame.error:
				self.sound = None

	def play(self) -> bool:
		if self._ready and self.sound is not None:
			try:
				self.sound.play()
				return True
			except pygame.error:
				self._ready = False
		return play_ring_native(self.path)


class PlannerView:
	"""Desktop planner and Pomodoro workspace backed by shared domain services."""

	def __init__(self, page: ft.Page, planner: Planner) -> None:
		self.page = page
		self.planner = planner
		self.timer = PomodoroTimer()
		self.selected_task_id: int | None = None
		self.timer_task_active = False
		self._timer_last_tick: float | None = None
		self.is_muted = False
		self.sound_player = SoundPlayer()

		self.task_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
		self.summary = ft.Text(size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)
		self.selected_task = ft.Text(
			"선택된 작업 없음",
			color=TEXT_MUTED,
			size=12,
			max_lines=1,
			overflow=ft.TextOverflow.ELLIPSIS,
		)
		self.title_input = ft.TextField(
			label="새 할 일",
			hint_text="예: 발표 자료 정리",
			on_submit=self.add_task,
			expand=True,
			filled=True,
			fill_color=SURFACE_ELEVATED,
			border_color=BORDER,
			focused_border_color=ACCENT_STRONG,
			label_style=ft.TextStyle(color=TEXT_MUTED),
			hint_style=ft.TextStyle(color=TEXT_MUTED),
			color=TEXT_PRIMARY,
			cursor_color=ACCENT,
		)
		self.phase_text = ft.Text(size=13, weight=ft.FontWeight.BOLD, color=ACCENT)
		self.timer_text = ft.Text(
			size=72,
			weight=ft.FontWeight.BOLD,
			color=TEXT_PRIMARY,
		)
		self.progress = ft.ProgressBar(
			value=1,
			width=240,
			bar_height=6,
			color=ACCENT,
			bgcolor=BORDER,
		)
		self.cycle_text = ft.Text(color=TEXT_MUTED, size=12)
		self.start_button = ft.ElevatedButton(
			"시작",
			icon=ft.Icons.PLAY_ARROW,
			on_click=self.toggle_timer,
			bgcolor=ACCENT,
			color=PAGE_BG,
			height=42,
		)
		self.mute_button = ft.IconButton(
			icon=ft.Icons.VOLUME_UP,
			icon_color=TEXT_MUTED,
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
					spacing=22,
					expand=True,
				),
				padding=ft.Padding(32, 28, 32, 28),
				bgcolor=PAGE_BG,
				expand=True,
			),
		)

	def build_header(self) -> ft.Control:
		return ft.ResponsiveRow(
			[
				ft.Column(
					[
						ft.Text("POPLA", size=12, weight=ft.FontWeight.BOLD, color=ACCENT_STRONG),
						ft.Text("오늘의 집중 데스크", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
						ft.Text(
							"할 일을 고르고, 한 번에 하나씩 끝내세요.",
							color=TEXT_MUTED,
							size=13,
						),
					],
					spacing=4,
					col={"sm": 12, "md": 8},
				),
				ft.Column(
					[
						ft.Container(
							content=ft.Column(
								[
									ft.Text("오늘의 진행", size=11, color=TEXT_MUTED),
									self.summary,
								],
								spacing=2,
							),
							bgcolor=SURFACE,
							border=ft.Border.all(1, BORDER),
							border_radius=10,
							padding=ft.Padding(16, 10, 16, 10),
						),
					],
					col={"sm": 12, "md": 4},
				),
			]
		)

	def build_planner_panel(self) -> ft.Control:
		return ft.Container(
			content=ft.Column(
				[
					ft.Row(
						[
							ft.Text("플래너", size=19, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
							ft.Container(
								content=self.selected_task,
								expand=True,
								alignment=ft.Alignment(1, 0),
							),
						],
						spacing=12,
						alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
					),
					ft.Row(
						[
							self.title_input,
							ft.IconButton(
								icon=ft.Icons.ADD,
								tooltip="할 일 추가",
								on_click=self.add_task,
								icon_color=ACCENT,
							),
						]
					),
					ft.Divider(height=1, color=BORDER),
					self.task_list,
				],
				spacing=16,
				expand=True,
			),
			padding=24,
			bgcolor=SURFACE,
			border=ft.Border.all(1, BORDER),
			border_radius=14,
			expand=True,
		)

	def build_pomodoro_panel(self) -> ft.Control:
		return ft.Container(
			content=ft.Column(
				[
					ft.Row(
						[
							ft.Text("포모도로", size=19, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
							self.phase_text,
						],
						alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
					),
					ft.Container(
						content=ft.Column(
							[
								self.timer_text,
								self.progress,
							],
							horizontal_alignment=ft.CrossAxisAlignment.CENTER,
							spacing=12,
						),
						padding=ft.Padding(16, 30, 16, 24),
						bgcolor=SURFACE_ELEVATED,
						border_radius=12,
					),
					ft.Container(content=self.cycle_text, alignment=ft.Alignment(0, 0)),
					ft.Row(
						[
							self.start_button,
							ft.IconButton(
								icon=ft.Icons.REFRESH,
								tooltip="타이머 초기화",
								on_click=self.reset_timer,
								icon_color=TEXT_MUTED,
							),
							ft.IconButton(
								icon=ft.Icons.SKIP_NEXT,
								tooltip="다음 단계",
								on_click=self.skip_phase,
								icon_color=TEXT_MUTED,
							),
							self.mute_button,
						],
						alignment=ft.MainAxisAlignment.CENTER,
					),
				],
				spacing=18,
				expand=True,
			),
			padding=24,
			bgcolor=SURFACE,
			border=ft.Border.all(1, BORDER),
			border_radius=14,
			expand=True,
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
		self.selected_task.color = ACCENT if selected else TEXT_MUTED
		self.task_list.controls = [self.task_row(task) for task in tasks]

	def refresh_timer(self) -> None:
		self.phase_text.value = PHASE_NAMES[self.timer.phase]
		self.timer_text.value = format_seconds(self.timer.state.remaining_seconds)
		self.progress.value = self.timer.state.remaining_seconds / self.timer.total_seconds
		self.cycle_text.value = f"완료한 집중 세션 {self.timer.state.cycle}회"
		self.start_button.text = "일시정지" if self.timer.is_running else "시작"
		self.start_button.icon = ft.Icons.PAUSE if self.timer.is_running else ft.Icons.PLAY_ARROW

	def task_row(self, task: Task) -> ft.Control:
		text_style = (
			ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH, color=TEXT_MUTED)
			if task.completed
			else None
		)
		is_selected = task.id == self.selected_task_id
		return ft.Container(
			content=ft.Row(
				[
					ft.Checkbox(value=task.completed, on_change=self.toggle_task, data=task.id),
					ft.Text(
						task.title,
						expand=True,
						selectable=True,
						style=text_style,
						color=TEXT_PRIMARY if not task.completed else None,
					),
					ft.IconButton(
						icon=ft.Icons.TIMER_OUTLINED,
						tooltip="이 작업에 집중",
						data=task.id,
						on_click=self.select_task,
						icon_color=ACCENT if is_selected else TEXT_MUTED,
					),
					ft.IconButton(
						icon=ft.Icons.DELETE_OUTLINE,
						tooltip="할 일 삭제",
						data=task.id,
						on_click=self.delete_task,
						icon_color=TEXT_MUTED,
					),
				],
				vertical_alignment=ft.CrossAxisAlignment.CENTER,
			),
			padding=ft.Padding(8, 5, 8, 5),
			bgcolor=ACCENT_SOFT if is_selected else SURFACE_ELEVATED,
			border=ft.Border.all(1, ACCENT_STRONG if is_selected else BORDER),
			border_radius=8,
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
			# Reset the reference point on every resume so paused time is not counted.
			self._timer_last_tick = time.monotonic()
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
			self.sound_player.play()
		self.refresh_timer()
		self.page.update()

	async def timer_loop(self) -> None:
		self._timer_last_tick = self._timer_last_tick or time.monotonic()
		last_displayed_second = ceil(self.timer.state.remaining_seconds)
		try:
			while self.timer.is_running:
				await asyncio.sleep(TIMER_POLL_INTERVAL)
				if not self.timer.is_running:
					break
				now = time.monotonic()
				last_tick = self._timer_last_tick or now
				transitioned = self.timer.tick(now - last_tick)
				self._timer_last_tick = now
				current_displayed_second = ceil(self.timer.state.remaining_seconds)
				should_refresh = (
					transitioned or current_displayed_second != last_displayed_second
				)
				if transitioned and not self.is_muted:
					self.sound_player.play()
				if should_refresh:
					self.refresh_timer()
					if transitioned:
						self.notify(f"{PHASE_NAMES[self.timer.phase]}이 시작되었습니다.", update=False)
					self.page.update()
					last_displayed_second = current_displayed_second
		finally:
			self.timer_task_active = False

	def notify(self, message: str, *, update: bool = True) -> None:
		self.page.snack_bar = ft.SnackBar(ft.Text(message))
		self.page.snack_bar.open = True
		if update:
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
	page.bgcolor = PAGE_BG
	page.padding = 0
	view = PlannerView(page, planner)
	page.add(view.build())
	view.refresh()
	page.update()


def run_app(planner: Planner) -> None:
	"""Start the cross-platform Flet desktop application."""
	ft.app(target=lambda page: create_page(page, planner))
