"""Hammer test: determine which of the two candidate aim-yaw angle fields
actually drives Wander's aim rotation.

Writes a sequence of angles (0, π/2, π, -π/2) to the target address for 2
seconds each. If the aim/Wander rotates to match, we've found the field.
"""
import os, sys, struct, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

import math

TARGETS = {
    "c858": 0x0106C858,
    "df00": 0x0106DF00,
}

ap = argparse.ArgumentParser()
ap.add_argument("which", choices=list(TARGETS.keys()))
args = ap.parse_args()

addr = TARGETS[args.which]

def f32(f): return struct.unpack('<I', struct.pack('<f', f))[0]

# Angles to cycle through (radians)
ANGLES = [0.0, math.pi / 2, math.pi, -math.pi / 2]

with PineClient() as pc:
    orig = pc.read_u32(addr)
    print(f"[*] Hammering 0x{addr:08X} with 4 angles, 2s each.")
    print(f"    Original: 0x{orig:08X} ({struct.unpack('<f', struct.pack('<I', orig))[0]:+.3f} rad)")
    print()
    try:
        for ang in ANGLES:
            w = f32(ang)
            print(f"    angle = {ang:+.3f} rad = {math.degrees(ang):+.0f}°  (writing 0x{w:08X})")
            t_end = time.monotonic() + 2.0
            writes = 0
            while time.monotonic() < t_end:
                pc.write_u32(addr, w)
                writes += 1
            print(f"      ...{writes} writes")
    finally:
        pc.write_u32(addr, orig)
        print(f"\n[*] Restored 0x{addr:08X} = 0x{orig:08X}")
