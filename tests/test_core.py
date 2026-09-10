import tempfile
import unittest
from pathlib import Path

from core.planner import Planner, PlannerStore
from core.pomodoro import Phase, PomodoroTimer, format_seconds


class PomodoroTimerTests(unittest.TestCase):
    def test_fractional_seconds_are_displayed_without_format_error(self) -> None:
        timer = PomodoroTimer(work_minutes=1, short_break_minutes=1, long_break_minutes=1)
        timer.start()

        self.assertFalse(timer.tick(0.1))
        self.assertEqual(timer.state.remaining_seconds, 59.9)
        self.assertEqual(format_seconds(timer.state.remaining_seconds), "01:00")

    def test_phase_transition_updates_cycle(self) -> None:
        timer = PomodoroTimer(work_minutes=1, short_break_minutes=1, long_break_minutes=1)
        timer.start()

        self.assertTrue(timer.tick(60))
        self.assertEqual(timer.phase, Phase.SHORT_BREAK)
        self.assertEqual(timer.state.cycle, 1)

    def test_paused_timer_does_not_advance(self) -> None:
        timer = PomodoroTimer(work_minutes=1, short_break_minutes=1, long_break_minutes=1)
        timer.start()
        timer.pause()

        self.assertFalse(timer.tick(30))
        self.assertEqual(timer.state.remaining_seconds, 60)


class PlannerTests(unittest.TestCase):
    def test_tasks_are_persisted_and_ids_remain_incremental(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            planner = Planner(PlannerStore(path))

            first = planner.add_task("  first task  ")
            second = planner.add_task("second task")
            planner.set_completed(first.id, True)
            planner.remove_task(first.id)

            self.assertEqual(second.id, 2)
            self.assertEqual(
                [(task.id, task.title, task.completed) for task in planner.list_tasks()],
                [(2, "second task", False)],
            )
            self.assertEqual(PlannerStore(path).load()[0].id, 2)


if __name__ == "__main__":
    unittest.main()
