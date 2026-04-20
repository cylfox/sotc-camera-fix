"""Poll candidate Wander-yaw fields in real time. Walk Wander in a circle
and see which addresses track his facing."""
import os, sys, struct, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CANDIDATES = [
    0x0106C83C, 0x0106C850, 0x0106C860,
    0x0106CB70,
    0x0106D010, 0x0106D018, 0x0106D020,
    0x0106D250,
    0x0106DF00,  # previously tested as "aim rotation", free-roam only
]

DUR = 10.0

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

with PineClient() as pc:
    print(f"[*] Polling {len(CANDIDATES)} candidate yaw fields for {DUR}s")
    print("    Walk Wander in a full circle during this time.\n")
    t0 = time.monotonic()
    mins = {a: float('inf') for a in CANDIDATES}
    maxs = {a: float('-inf') for a in CANDIDATES}
    prev = {a: None for a in CANDIDATES}
    max_jump = {a: 0.0 for a in CANDIDATES}
    while time.monotonic() - t0 < DUR:
        for a in CANDIDATES:
            v = asf(pc.read_u32(a))
            mins[a] = min(mins[a], v)
            maxs[a] = max(maxs[a], v)
            if prev[a] is not None:
                jmp = abs(v - prev[a])
                if 0.01 < jmp < 6.0:  # ignore ±2π wraps (>6) and noise (<0.01)
                    max_jump[a] = max(max_jump[a], jmp)
            prev[a] = v
        time.sleep(0.02)

    print(f"\n    addr          min       max       range     max_jump   final")
    for a in CANDIDATES:
        print(f"    0x{a:08X}  {mins[a]:+.4f}  {maxs[a]:+.4f}  {maxs[a]-mins[a]:.4f}  "
              f"{max_jump[a]:+.4f}   {prev[a]:+.4f}")
