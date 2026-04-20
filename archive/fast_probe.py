"""High-frequency poll of a tight memory region to catch transient writes.

Reads 64 bytes every ~5ms for N seconds. Far smaller window than scenario_run
but much higher temporal resolution — good for spotting values that are
written briefly each frame.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

from pine_client import PineClient, DEFAULT_SLOT

OUT_DIR = Path(r"C:\Users\Marcos\sotc\scenarios")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=0x01C182D0)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x40)
    ap.add_argument("--duration", type=float, default=8.0)
    ap.add_argument("--pre-delay", type=float, default=3.0)
    args = ap.parse_args()

    assert args.size % 8 == 0
    n_words = args.size // 4
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[*] Fast probe '{args.name}': 0x{args.addr:08X}..+0x{args.size:X} "
          f"for {args.duration}s (as fast as PINE allows)")
    if args.pre_delay > 0:
        for i in range(int(args.pre_delay), 0, -1):
            print(f"    refocus PCSX2 and perform the action... starting in {i}")
            time.sleep(1.0)

    samples: list[tuple[float, list[int]]] = []
    t_start = time.monotonic()
    end = t_start + args.duration
    with PineClient(args.host if hasattr(args, "host") else "127.0.0.1",
                    DEFAULT_SLOT) as pc:
        while time.monotonic() < end:
            t = time.monotonic() - t_start
            raw = pc.read_bytes(args.addr, args.size)
            row = list(struct.unpack(f"<{n_words}I", raw))
            samples.append((t, row))

    total = time.monotonic() - t_start
    print(f"[*] Captured {len(samples)} samples in {total:.2f}s "
          f"(effective rate: {len(samples)/total:.0f} Hz)")

    # Identify changing offsets
    if samples:
        cols = list(zip(*[row for _, row in samples]))
        changed = [(i, len(set(c))) for i, c in enumerate(cols) if len(set(c)) > 1]
        print(f"[*] Offsets that changed: {len(changed)}/{n_words}")
        for i, uniq in changed[:30]:
            col = cols[i]
            floats = [struct.unpack("<f", struct.pack("<I", v))[0] for v in col]
            print(f"    +0x{4*i:04X}  uniq={uniq:3d}  "
                  f"first=0x{col[0]:08X} ({floats[0]:+.4f})  "
                  f"last=0x{col[-1]:08X} ({floats[-1]:+.4f})  "
                  f"f_range={max(floats)-min(floats):+.4g}")

    out_path = OUT_DIR / f"fast_{args.name}.json"
    with out_path.open("w") as f:
        json.dump({
            "addr": args.addr, "size": args.size,
            "duration": args.duration,
            "samples": [{"t": t, "vals": row} for t, row in samples],
        }, f)
    print(f"[*] Saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
