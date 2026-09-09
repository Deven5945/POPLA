"""Fast, controllable Pomodoro runner for testing the timer flow.

Examples:
    python pomodoro_test_runner.py --speed 60 --cycles 2
    python pomodoro_test_runner.py --speed 120 --cycles 4 --skip work
    python pomodoro_test_runner.py --work 0.02 --short 0.01 --long 0.02
"""

import argparse
import math
import time

from core.pomodoro import long_break, short_break, work_time


PHASES = ("work", "short", "long")


class TestTimer:
    """A timer simulator with accelerated time and phase skipping."""

    def __init__(self, work, short, long, speed, skipped):
        self.durations = {
            "work": work * 60,
            "short": short * 60,
            "long": long * 60,
        }
        self.speed = speed
        self.skipped = set(skipped)

    def start(self, cycles):
        for cycle in range(1, cycles + 1):
            self.run_phase("work", cycle)

            break_phase = "long" if cycle % 4 == 0 else "short"
            self.run_phase(break_phase, cycle)

        print(f"완료: {cycles}개 사이클")

    def run_phase(self, phase, cycle):
        if phase in self.skipped or "all" in self.skipped:
            print(f"[{cycle}] {phase}: skip")
            return

        seconds = self.durations[phase]
        print(f"[{cycle}] {phase}: start ({seconds:g} simulated seconds)")
        self.countdown(seconds, phase)
        print(f"[{cycle}] {phase}: done")

    def countdown(self, seconds, phase):
        remaining = seconds
        while remaining > 0:
            display_seconds = max(1, math.ceil(remaining))
            minutes, display_seconds = divmod(display_seconds, 60)
            print(f"  {phase:5} {minutes:02d}:{display_seconds:02d}", end="\r")

            real_seconds = min(1, remaining) / self.speed
            time.sleep(real_seconds)
            remaining -= 1

        print(" " * 24, end="\r")


def parse_args():
    parser = argparse.ArgumentParser(description="빠른 Pomodoro 테스트 실행기")
    parser.add_argument(
        "--speed",
        type=float,
        default=60,
        help="시간 배수. 60이면 시뮬레이션 1초가 실제 1/60초 (기본값: 60)",
    )
    parser.add_argument(
        "--cycles", type=int, default=1, help="실행할 사이클 수 (기본값: 1)"
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        choices=(*PHASES, "all"),
        default=(),
        help="건너뛸 단계: work, short, long, all",
    )
    parser.add_argument("--work", type=float, default=work_time, help="작업 시간(분)")
    parser.add_argument("--short", type=float, default=short_break, help="짧은 휴식(분)")
    parser.add_argument("--long", type=float, default=long_break, help="긴 휴식(분)")
    args = parser.parse_args()

    if args.speed <= 0:
        parser.error("--speed는 0보다 커야 합니다.")
    if args.cycles <= 0:
        parser.error("--cycles는 0보다 커야 합니다.")
    if min(args.work, args.short, args.long) < 0:
        parser.error("시간은 음수가 될 수 없습니다.")

    return args


def main():
    args = parse_args()
    timer = TestTimer(
        work=args.work,
        short=args.short,
        long=args.long,
        speed=args.speed,
        skipped=args.skip,
    )
    timer.start(args.cycles)


if __name__ == "__main__":
    main()