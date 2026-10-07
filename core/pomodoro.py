from dataclasses import dataclass
from enum import Enum
import math
from numbers import Real

# 시간 설정
WORK_MINUTES = 25
SHORT_BREAK_MINUTES = 5
LONG_BREAK_MINUTES = 15

# 상태 설정
class Phase(str, Enum):
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"

# 상태 클래스
@dataclass
class PomodoroState:
    phase: Phase
    cycle: int
    remaining_seconds: float
    running: bool = False

# 포모도로 클래스
class PomodoroTimer:
    def __init__(
        self,
        work_minutes: int = WORK_MINUTES,
        short_break_minutes: int = SHORT_BREAK_MINUTES,
        long_break_minutes: int = LONG_BREAK_MINUTES,
    ) -> None:
        if min(work_minutes, short_break_minutes, long_break_minutes) <= 0:
            raise ValueError("시간 0보다 작음")
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

    # 페이즈, 실행 여부, 총 시간 반환
    @property
    def phase(self) -> Phase:
        return self.state.phase

    @property
    def is_running(self) -> bool:
        return self.state.running

    @property
    def total_seconds(self) -> int:
        return self.durations[self.phase]

    # 시작, 일시정지, 리셋, 스킵, 틱
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

    def tick(self, seconds: float = 1.0) -> bool:
        if not isinstance(seconds, Real) or isinstance(seconds, bool) or not math.isfinite(seconds):
            raise ValueError("시간이 숫자가 아님")
        seconds = float(seconds)
        if seconds < 0:
            raise ValueError("시간이 음수임")
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

    # 페이즈 전환
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

# 시간 포맷
def format_seconds(seconds: float) -> str:
    display_seconds = math.ceil(max(0.0, seconds))
    minutes, remaining_seconds = divmod(display_seconds, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"
