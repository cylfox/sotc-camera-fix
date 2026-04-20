"""Poll candidate camera-yaw angle fields during aim-mode while the user
rotates the camera with right stick. The one that tracks smoothly is
the live camera yaw."""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CANDIDATES = [
    0x0106C858,  # free-roam camera yaw (confirmed driver in free-roam)
    0x0106DF00,  # found in aim_neutral vs aim_rotating diff
    0x0106DF0C,  # nearby small-delta
    0x0106C188,
    0x0106C1C8,
    0x0106C208,
    0x0106C288,
    0x0106C834,
    0x0106C838,
    0x0106CA9C,  # float
]

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

DUR = 10.0
with PineClient() as pc:
    print(f"[*] In aim mode, rotate the camera with the RIGHT stick during the next {DUR}s.")
    print(f"    Polling {len(CANDIDATES)} candidates.\n")
    t0 = time.monotonic()
    mins = {a: float('inf') for a in CANDIDATES}
    maxs = {a: float('-inf') for a in CANDIDATES}
    starts = {}
    last = {}
    total_change = {a: 0.0 for a in CANDIDATES}
    while time.monotonic() - t0 < DUR:
        for a in CANDIDATES:
            v = asf(pc.read_u32(a))
            if a not in starts:
                starts[a] = v
            mins[a] = min(mins[a], v)
            maxs[a] = max(maxs[a], v)
            if a in last:
                delta = abs(v - last[a])
                if delta < 4.0:  # filter out ±2π wraps
                    total_change[a] += delta
            last[a] = v
        time.sleep(0.02)

    print(f"\n    addr          start    end      range     total-motion  final")
    for a in CANDIDATES:
        print(f"    0x{a:08X}  {starts[a]:+.4f}  {last[a]:+.4f}  "
              f"{maxs[a]-mins[a]:.4f}   {total_change[a]:.4f}")
