import json
from pathlib import Path
import tempfile
import unittest

from core.planner import Planner, PlannerStore
from core.pomodoro import Phase, PomodoroTimer, format_seconds


class PlannerStoreTests(unittest.TestCase):
    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            store = PlannerStore(path)
            planner = Planner(store)

            task = planner.add_task("  중요한 작업  ")

            self.assertEqual(task.title, "중요한 작업")
            self.assertEqual(store.load(), [task])

    def test_invalid_task_data_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(
                json.dumps({"tasks": [{"id": 1, "title": "작업", "completed": "false"}]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "completed"):
                PlannerStore(path).load()

    def test_duplicate_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"id": 1, "title": "첫 번째"},
                            {"id": 1, "title": "두 번째"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "중복"):
                PlannerStore(path).load()


class PomodoroTimerTests(unittest.TestCase):
    def test_elapsed_time_is_applied_with_subsecond_precision(self) -> None:
        timer = PomodoroTimer(work_minutes=1, short_break_minutes=1, long_break_minutes=1)
        timer.start()

        self.assertFalse(timer.tick(0.25))
        self.assertAlmostEqual(timer.state.remaining_seconds, 59.75)

    def test_tick_crosses_multiple_phase_boundaries(self) -> None:
        timer = PomodoroTimer(work_minutes=1, short_break_minutes=1, long_break_minutes=1)
        timer.start()

        self.assertTrue(timer.tick(120))
        self.assertEqual(timer.phase, Phase.WORK)
        self.assertEqual(timer.state.cycle, 1)
        self.assertEqual(timer.state.remaining_seconds, 60)

    def test_format_seconds_rounds_up_for_countdown_display(self) -> None:
        self.assertEqual(format_seconds(59.1), "01:00")
        self.assertEqual(format_seconds(0), "00:00")


if __name__ == "__main__":
    unittest.main()
