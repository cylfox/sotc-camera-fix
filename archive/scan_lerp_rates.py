"""Scan heap for common auto-focus/lerp rate float constants near the camera region."""
import sys, struct
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

# Common lerp/pull rates in camera/animation code
RATE_VALUES = [
    # Direct pull-strengths
    0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.0625,
    0.075, 0.0833, 0.1, 0.125, 0.15, 0.167, 0.175, 0.2, 0.25, 0.3, 0.333, 0.4, 0.5,
    # Retention complements (1 - pull)
    0.9, 0.92, 0.925, 0.95, 0.96, 0.975, 0.98, 0.99,
    # Common specific values
    0.0352, 0.03125,  # seen in observations
]
TARGETS = {}
for v in RATE_VALUES:
    TARGETS[struct.unpack('<I', struct.pack('<f', v))[0]] = v
    TARGETS[struct.unpack('<I', struct.pack('<f', -v))[0]] = -v

# Tolerance of 2 ULPs
TOL = 4

regions = [
    (0x0106A000, 0x8000),      # around camera pose struct 0x0106E5D0
    (0x0106C000, 0x4000),      # around virtual stick 0x0106C100
    (0x01C18000, 0x2000),      # around live controller 0x01C18890
    (0x01477000, 0x2000),      # around the earlier 0x01477xxx area
    (0x0130D000, 0x8000),      # around entity 0x01301760
    (0x0013A500, 0x200),       # pad buffer area
]

def main():
    hits = []
    with PineClient() as pc:
        for base, size in regions:
            print(f'scan 0x{base:08X}..+{size:X}', flush=True)
            addr = base
            end = base + size
            while addr < end:
                cs = min(0x8000, end - addr)
                chunk = pc.read_bytes(addr, cs)
                for off in range(0, cs, 4):
                    v = struct.unpack_from('<I', chunk, off)[0]
                    # Exact match
                    if v in TARGETS:
                        hits.append((addr + off, v, TARGETS[v]))
                        continue
                    # Tolerance match: check if within TOL ULPs of any target
                    for t, val in TARGETS.items():
                        if abs(v - t) <= TOL and v != 0:
                            hits.append((addr + off, v, val))
                            break
                addr += cs
    print(f'\nTotal hits: {len(hits)}')
    # Group by value
    by_val = {}
    for a, raw, val in hits:
        by_val.setdefault(val, []).append((a, raw))
    for val in sorted(by_val.keys()):
        locs = by_val[val]
        print(f'\n{val:+.4f}  ({len(locs)} location(s)):')
        for a, raw in locs:
            print(f'  0x{a:08X}  (0x{raw:08X})')

if __name__ == "__main__":
    main()
