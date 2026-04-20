"""Poll pad stick bytes to identify which byte = which stick axis."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

# Pad buffer at 0x0013A69E contains 4 stick bytes
BASE = 0x0013A69E
OFFSETS = list(range(0, 8))

DUR = 20.0

with PineClient() as pc:
    print(f"[*] Polling 8 bytes at 0x{BASE:08X} for {DUR:.0f}s")
    print("    Sequence: LEFT X-axis wiggle, LEFT Y-axis, RIGHT X, RIGHT Y (4s each).")
    t0 = time.monotonic()
    mins = {o: 255 for o in OFFSETS}
    maxs = {o: 0 for o in OFFSETS}
    while time.monotonic() - t0 < DUR:
        for o in OFFSETS:
            v = pc.read_u8(BASE + o)
            mins[o] = min(mins[o], v)
            maxs[o] = max(maxs[o], v)
        time.sleep(0.02)
    print(f"\n    offset  addr          min   max   range  behavior")
    for o in OFFSETS:
        tag = "   <-- responsive" if maxs[o] - mins[o] > 20 else ""
        print(f"    +0x{o:02X}   0x{BASE+o:08X}  0x{mins[o]:02X}  0x{maxs[o]:02X}  {maxs[o]-mins[o]:3d}{tag}")
