"""Hammer write a fixed value to a list of candidate addresses.

Choose a preset group with the first arg.

Usage:
  py tools/hammer_letterbox.py <group> [duration_s]

Groups:
  alpha     - bars=1, nobars=0  (write 0.0)        [tested, no effect]
  inverted  - bars=0, nobars=1  (write 1.0)
  swing     - non-saturated transitions (write the gameplay value)
  all       - inverted + swing combined

Run during a cutscene with bars visible. If bars vanish, dim, or
glitch, the alpha is in that group. Cutscene playback may also
break visibly — that's how we know we hit something.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

ZERO_F32 = 0x00000000
ONE_F32 = 0x3F800000

# Each entry: (addr, value_to_write_u32, comment)
GROUPS = {
    "alpha": [
        (0x010644DC, ZERO_F32, "bars=1.0 -> force 0.0"),
        (0x010645AC, ZERO_F32, "bars=1.0 -> force 0.0"),
        (0x010698AC, ZERO_F32, "bars=1.0 -> force 0.0"),
    ],
    "inverted": [
        (0x010644EC, ONE_F32, "bars=0.0 -> force 1.0"),
        (0x0106451C, ONE_F32, "bars=0.0 -> force 1.0"),
        (0x01064548, ONE_F32, "bars=0.0 -> force 1.0"),
        (0x010645BC, ONE_F32, "bars=0.0 -> force 1.0"),
        (0x01069A6C, ONE_F32, "bars=0.0 -> force 1.0"),
        (0x01D03A4C, ONE_F32, "bars=0.0 -> force 1.0"),
        (0x01D03ADC, ONE_F32, "bars=0.0 -> force 1.0"),
    ],
    "swing": [
        # Force the cutscene values to their gameplay values
        (0x0106994C, 0x3EAAEAFB, "bars=1.0 -> force ~0.334 (gameplay value)"),
        (0x01069A04, 0x3F0227F4, "bars=0.0 -> force ~0.508 (gameplay value)"),
    ],
}
GROUPS["all"] = GROUPS["inverted"] + GROUPS["swing"]

# HUD/UI struct cluster — 9 values in a tight 632-byte block at 0x01477xxx.
# Strategy: force them to their nobars (gameplay) values during the cutscene.
# If bars vanish, the alpha (or its surrogate) is in this struct.
F_0_9 = 0x3F666666   # 0.9
GROUPS["hud"] = [
    (0x014774E8, ONE_F32, "0->1 (force gameplay value)"),
    (0x01477500, ONE_F32, "0->1"),
    (0x01477504, ZERO_F32, "1->0"),
    (0x01477508, ZERO_F32, "1->0"),
    (0x01477290, F_0_9, "1.0 -> 0.9 (gameplay value)"),
    (0x01477298, F_0_9, "1.0 -> 0.9"),
    (0x01477484, F_0_9, "1.0 -> 0.9"),
    (0x014772B0, 0x3F1A4396, "0.42 -> 0.60 (gameplay value)"),
    (0x01477458, 0x3F549DBA, "0.20 -> 0.83 (gameplay value)"),
]
# Just the booleans subset, in case those alone control bar visibility
GROUPS["hud_bool"] = GROUPS["hud"][:4]
# Just the swing subset
GROUPS["hud_swing"] = GROUPS["hud"][4:]
# Bisecting hud_bool
GROUPS["hud_bool_a"] = GROUPS["hud"][:2]   # 0x014774E8, 0x01477500 (0->1)
GROUPS["hud_bool_b"] = GROUPS["hud"][2:4]  # 0x01477504, 0x01477508 (1->0)
# Bisect hud_bool_b
GROUPS["hud_b1"] = [GROUPS["hud"][2]]      # 0x01477504 only
GROUPS["hud_b2"] = [GROUPS["hud"][3]]      # 0x01477508 only


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in GROUPS:
        print("usage: hammer_letterbox.py <group> [duration_s]")
        print(f"groups: {', '.join(GROUPS.keys())}")
        sys.exit(2)
    group = sys.argv[1]
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    targets = GROUPS[group]

    with PineClient() as pc:
        print(f"[*] Group '{group}': {len(targets)} addrs")
        for addr, val, note in targets:
            cur_raw = pc.read_u32(addr)
            cur_f = struct.unpack("<f", struct.pack("<I", cur_raw))[0]
            new_f = struct.unpack("<f", struct.pack("<I", val))[0]
            print(f"  0x{addr:08X}: cur={cur_f:+.4f}  -> writing {new_f:+.4f}  ({note})")
        print(f"[*] Hammering for {duration:.1f}s. Watch the screen.")
        t0 = time.monotonic()
        cycles = 0
        while time.monotonic() - t0 < duration:
            for addr, val, _ in targets:
                pc.write_u32(addr, val)
            cycles += 1
        elapsed = time.monotonic() - t0
        print(f"[*] Done. {cycles} cycles, ~{cycles*len(targets)/elapsed:.0f} writes/sec.")


if __name__ == "__main__":
    main()
