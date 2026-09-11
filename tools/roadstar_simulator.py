#!/usr/bin/env python3
"""Run the deterministic RoadStar Dock/HOS Collision simulator."""
from __future__ import annotations

import argparse
import json
import time

from otp.roadstar_simulator import RoadStarSimulator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="wait between samples")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between live samples")
    args = parser.parse_args()

    simulator = RoadStarSimulator()
    for telemetry in simulator.stream():
        print(json.dumps(telemetry.as_dict(), sort_keys=True), flush=True)
        if args.live:
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
