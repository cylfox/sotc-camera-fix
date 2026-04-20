"""Poll the three early-gate state variables in 0x0118E030.

Gates (from disasm):
  1. bit-24 of qword at 0x0071F2D8   -- bnez at 0x0118E07C
  2. u32   at 0x0128FDB4              -- beql zero at 0x0118E088
  3. float at 0x014779F0               -- (0.0 < f) check, bc1fl at 0x0118E0A0
"""

from __future__ import annotations

import argparse
import struct
import sys
import time

from pine_client import PineClient, DEFAULT_SLOT

GATE1_QWORD_ADDR = 0x0071F2D8
GATE2_U32_ADDR = 0x0128FDB4
GATE3_FLOAT_ADDR = 0x014779F0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--hz", type=float, default=60.0)
    ap.add_argument("--pre-delay", type=float, default=3.0)
    args = ap.parse_args()

    print(f"Polling 3 gate states for {args.duration}s @ {args.hz} Hz")
    if args.pre_delay > 0:
        for i in range(int(args.pre_delay), 0, -1):
            print(f"    refocus PCSX2 and perform the action... starting in {i}")
            time.sleep(1.0)
    print(f"{'t':>6}  {'gate1_bit24':>11}  {'gate2_u32':>12}  {'gate3_float':>12}  "
          f"{'ALL_PASS':>8}")
    print("-" * 64)

    interval = 1.0 / args.hz
    t_end = time.monotonic() + args.duration
    last_g1 = last_g2 = last_g3 = None
    changes = []
    with PineClient() as pc:
        t_start = time.monotonic()
        while time.monotonic() < t_end:
            t0 = time.monotonic()
            q = pc.read_u64(GATE1_QWORD_ADDR)
            g1_bit24 = (q >> 24) & 1
            g2 = pc.read_u32(GATE2_U32_ADDR)
            g3_raw = pc.read_u32(GATE3_FLOAT_ADDR)
            g3 = struct.unpack("<f", struct.pack("<I", g3_raw))[0]
            # Gate passes if: g1_bit24 == 0 AND g2 != 0 AND g3 > 0.0
            all_pass = (g1_bit24 == 0) and (g2 != 0) and (g3 > 0.0)
            t = time.monotonic() - t_start
            # Only print if anything changed from last tick
            if (g1_bit24, g2, g3_raw) != (last_g1, last_g2, last_g3):
                print(f"{t:>6.2f}  {g1_bit24:>11d}  0x{g2:08X}  {g3:+12.4g}  "
                      f"{str(all_pass):>8}  <-- CHANGED" if last_g1 is not None else
                      f"{t:>6.2f}  {g1_bit24:>11d}  0x{g2:08X}  {g3:+12.4g}  "
                      f"{str(all_pass):>8}")
                last_g1, last_g2, last_g3 = g1_bit24, g2, g3_raw
            slack = interval - (time.monotonic() - t0)
            if slack > 0:
                time.sleep(slack)
    return 0


if __name__ == "__main__":
    sys.exit(main())
