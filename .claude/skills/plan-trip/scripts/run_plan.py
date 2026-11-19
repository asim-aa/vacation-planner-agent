"""Run the vacation-planner pipeline and print the final state as JSON."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from agents.graph import plan_trip  # noqa: E402


def main() -> int:
    request = " ".join(sys.argv[1:]).strip()
    if not request:
        print("usage: run_plan.py '<trip request>'", file=sys.stderr)
        return 2
    state = plan_trip(request)
    json.dump(state, sys.stdout, indent=2, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
