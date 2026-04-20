"""Poll the camera forward vector and nearby pose-struct fields to see
what's live right now. Prints each candidate along with its float
interpretation and vector magnitude (for unit-vector detection)."""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

# Known addresses from prior research (live heap, session-dependent)
FIELDS = [
    ("camera pose forward",      0x0106E7C0, 3),
    ("camera pose up",           0x0106E800, 3),
    ("camera pose position",     0x0106E600, 3),
    ("camera live ctrl target",  0x01C18710, 3),   # output camera X/Y/Z from earlier research
    ("direction buffer L1",      0x0106C230, 3),
    ("direction buffer L2",      0x0106C1F0, 3),
    ("direction buffer L3",      0x0106C1B0, 3),
]

DUR = 4.0

def as_f(w):
    return struct.unpack('<f', struct.pack('<I', w))[0]

with PineClient() as pc:
    t0 = time.monotonic()
    n = 0
    last = {}
    flips = {k[0]: 0 for k in FIELDS}
    while time.monotonic() - t0 < DUR:
        for name, addr, count in FIELDS:
            cur = tuple(pc.read_u32(addr + 4*i) for i in range(count))
            if name in last and last[name] != cur:
                flips[name] += 1
            last[name] = cur
        n += 1
    print(f"[*] {n} polls over {DUR:.1f}s, {n/DUR:.0f} Hz")
    print()
    for name, addr, count in FIELDS:
        vals = last[name]
        floats = tuple(as_f(w) for w in vals)
        mag = sum(f*f for f in floats) ** 0.5
        tag = " [UNIT]" if 0.98 < mag < 1.02 else ""
        print(f"  0x{addr:08X}  {name}")
        print(f"    last = {', '.join(f'{f:+.4f}' for f in floats)}  |v|={mag:.3f}{tag}")
        print(f"    flips during poll: {flips[name]}")
