#!/usr/bin/env python3
"""Validate the fictional policy and evaluation data without extra packages."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentops_api.demo_data import load_demo_bundle, validate_demo_bundle  # noqa: E402


bundle = load_demo_bundle()
errors = validate_demo_bundle(bundle)
if errors:
    print("Demo data validation failed:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print(
    f"Demo data valid: {len(bundle['policies'])} policy documents, "
    f"{len(bundle['cases_document']['cases'])} labeled cases."
)
