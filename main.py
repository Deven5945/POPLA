"""Application entry point."""

from pathlib import Path

from core.planner import Planner, PlannerStore
from core.ui import run_app


DEFAULT_PLAN_PATH = Path(__file__).parent / "saves" / "plan.json"


def main() -> None:
    """Start the POPLA desktop application."""
    run_app(Planner(PlannerStore(DEFAULT_PLAN_PATH)))


if __name__ == "__main__":
    main()