"""UI-independent Pomodoro state machine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


WORK_MINUTES = 25
SHORT_BREAK_MINUTES = 5
LONG_BREAK_MINUTES = 15

class Phase(str, Enum):
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


@dataclass
class PomodoroState:
    phase: Phase
    cycle: int
    remaining_seconds: int
    running: bool = False


class PomodoroTimer:
    """Deterministic timer state that can be driven by any UI event loop."""

    def __init__(
        self,
        work_minutes: int = WORK_MINUTES,
        short_break_minutes: int = SHORT_BREAK_MINUTES,
        long_break_minutes: int = LONG_BREAK_MINUTES,
    ) -> None:
        if min(work_minutes, short_break_minutes, long_break_minutes) <= 0:
            raise ValueError("포모도로 시간은 0보다 커야 합니다.")
        self.durations = {
            Phase.WORK: work_minutes * 60,
            Phase.SHORT_BREAK: short_break_minutes * 60,
            Phase.LONG_BREAK: long_break_minutes * 60,
        }
        self.state = PomodoroState(
            phase=Phase.WORK,
            cycle=0,
            remaining_seconds=self.durations[Phase.WORK],
        )

    @property
    def phase(self) -> Phase:
        return self.state.phase

    @property
    def is_running(self) -> bool:
        return self.state.running

    @property
    def total_seconds(self) -> int:
        return self.durations[self.phase]

    def start(self) -> None:
        self.state.running = True

    def pause(self) -> None:
        self.state.running = False

    def reset(self) -> None:
        self.state = PomodoroState(
            phase=Phase.WORK,
            cycle=self.state.cycle,
            remaining_seconds=self.durations[Phase.WORK],
        )

    def skip(self) -> None:
        self._advance_phase()

    def tick(self, seconds: int = 1) -> bool:
        """Advance time and return whether a phase boundary was crossed."""
        if seconds < 0:
            raise ValueError("경과 시간은 음수가 될 수 없습니다.")
        if not self.is_running or seconds == 0:
            return False

        transitioned = False
        while seconds >= self.state.remaining_seconds:
            seconds -= self.state.remaining_seconds
            self._advance_phase()
            transitioned = True
            if seconds == 0:
                break
        self.state.remaining_seconds -= seconds
        return transitioned

    def _advance_phase(self) -> None:
        if self.phase == Phase.WORK:
            cycle = self.state.cycle + 1
            phase = Phase.LONG_BREAK if cycle % 4 == 0 else Phase.SHORT_BREAK
        else:
            cycle = self.state.cycle
            phase = Phase.WORK
        self.state = PomodoroState(
            phase=phase,
            cycle=cycle,
            remaining_seconds=self.durations[phase],
            running=self.state.running,
        )


def format_seconds(seconds: int) -> str:
    minutes, remaining_seconds = divmod(max(0, seconds), 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"
