"""Poll candidate mode flags for extended duration, tally unique values."""
import sys, time
from collections import Counter
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

CANDIDATES = [
    0x01C18CBC,  # flag word
    0x01C18CC0,  # lower 16 bits differed
    0x01C18D60,  # pointer that changed
]

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0

counters = {a: Counter() for a in CANDIDATES}

with PineClient() as pc:
    t0 = time.monotonic()
    n = 0
    while time.monotonic() - t0 < DURATION:
        for a in CANDIDATES:
            v = pc.read_u32(a)
            counters[a][v] += 1
        n += 1
        time.sleep(0.01)

print(f"[*] {n} samples over {DURATION:.1f}s\n")
for a in CANDIDATES:
    print(f"0x{a:08X}  ({len(counters[a])} unique values):")
    for v, c in sorted(counters[a].items(), key=lambda kv: -kv[1]):
        pct = 100.0 * c / n
        print(f"  0x{v:08X}  ({c} / {pct:.1f}%)")
    print()
