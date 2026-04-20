"""Hammer test: does writing to a candidate Wander-facing angle field
actually rotate Wander?
"""
import os, sys, struct, time, argparse, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

ap = argparse.ArgumentParser()
ap.add_argument("addr", help="hex address")
args = ap.parse_args()

addr = int(args.addr, 16)

def f32(f): return struct.unpack('<I', struct.pack('<f', f))[0]

ANGLES = [0.0, math.pi/2, math.pi, -math.pi/2]

with PineClient() as pc:
    orig = pc.read_u32(addr)
    print(f"[*] Hammering 0x{addr:08X} with 4 angles, 2s each.")
    print(f"    Original: 0x{orig:08X} ({struct.unpack('<f', struct.pack('<I', orig))[0]:+.3f} rad)")
    try:
        for ang in ANGLES:
            w = f32(ang)
            print(f"    angle = {ang:+.3f} rad = {math.degrees(ang):+.0f} deg  (writing 0x{w:08X})")
            t_end = time.monotonic() + 2.0
            while time.monotonic() < t_end:
                pc.write_u32(addr, w)
    finally:
        pc.write_u32(addr, orig)
        print(f"\n[*] Restored.")
