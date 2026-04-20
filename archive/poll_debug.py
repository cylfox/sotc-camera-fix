"""Poll the debug-trampoline log addresses at high freq to see all values
the pad-read function is called with."""
import sys, time
from collections import Counter
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

LOG_S0 = 0x001A4A30
LOG_RA = 0x001A4A34

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0

s0_counts = Counter()
ra_counts = Counter()

with PineClient() as pc:
    t0 = time.monotonic()
    n = 0
    while time.monotonic() - t0 < DURATION:
        s0 = pc.read_u32(LOG_S0)
        ra = pc.read_u32(LOG_RA)
        s0_counts[s0] += 1
        ra_counts[ra] += 1
        n += 1
    print(f"[*] {n} samples in {time.monotonic() - t0:.1f}s")
    print(f"\nUnique $s0 values:")
    for v, c in sorted(s0_counts.items(), key=lambda kv: -kv[1]):
        print(f"  0x{v:08X}  ({c} samples)")
    print(f"\nUnique $ra values:")
    for v, c in sorted(ra_counts.items(), key=lambda kv: -kv[1]):
        print(f"  0x{v:08X}  ({c} samples)")
