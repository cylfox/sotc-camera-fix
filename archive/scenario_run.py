"""Poll the camera controller struct for one scenario and write samples to JSON.

Usage:
    py scenario_run.py <scenario_name> [--duration 5] [--hz 30] [--size 0x400]
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

from pine_client import PineClient, DEFAULT_SLOT

CONTROLLER_BASE = 0x01C180A0
OUT_DIR = Path(r"C:\Users\Marcos\sotc\scenarios")


def poll_struct(pc: PineClient, base: int, size: int, duration_s: float, hz: float) -> list[list[int]]:
    """Return list of snapshots, each a list of n 32-bit words."""
    assert size % 4 == 0
    n_words = size // 4
    interval = 1.0 / hz
    end = time.monotonic() + duration_s
    samples: list[list[int]] = []
    while time.monotonic() < end:
        t0 = time.monotonic()
        raw = pc.read_bytes(base, size)
        row = list(struct.unpack(f"<{n_words}I", raw))
        samples.append(row)
        slack = interval - (time.monotonic() - t0)
        if slack > 0:
            time.sleep(slack)
    return samples


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", help="name, e.g. idle / yaw / pitch / walk")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_SLOT)
    ap.add_argument("--base", type=lambda s: int(s, 0), default=CONTROLLER_BASE)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x800)
    ap.add_argument("--duration", type=float, default=5.0)
    ap.add_argument("--hz", type=float, default=20.0)
    ap.add_argument("--pre-delay", type=float, default=3.0,
                    help="seconds to wait before polling starts (refocus PCSX2)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{args.scenario}.json"

    print(f"[*] Scenario '{args.scenario}': polling 0x{args.base:08X}..+0x{args.size:X} "
          f"for {args.duration}s @ {args.hz:g} Hz")
    if args.pre_delay > 0:
        for i in range(int(args.pre_delay), 0, -1):
            print(f"    refocus PCSX2 and perform the action... starting in {i}")
            time.sleep(1.0)
    t_start = time.monotonic()
    with PineClient(args.host, args.port) as pc:
        samples = poll_struct(pc, args.base, args.size, args.duration, args.hz)
    wall = time.monotonic() - t_start
    print(f"[*] Captured {len(samples)} samples in {wall:.2f}s "
          f"(effective rate: {len(samples)/wall:.1f} Hz)")

    out = {
        "scenario": args.scenario,
        "base": args.base,
        "size": args.size,
        "hz": args.hz,
        "duration": args.duration,
        "n_samples": len(samples),
        "samples": samples,
    }
    with out_path.open("w") as f:
        json.dump(out, f)
    print(f"[*] Saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
