#!/usr/bin/env python3
"""Run the offline Stage 5 evaluation on the fictional labeled cases."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentops_api.demo_data import load_demo_bundle, validate_demo_bundle  # noqa: E402
from agentops_api.evaluation import evaluate_bundle  # noqa: E402


def main() -> int:
    bundle = load_demo_bundle()
    errors = validate_demo_bundle(bundle)
    if errors:
        print("Evaluation stopped: demo data failed validation.", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    report = evaluate_bundle(bundle)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
