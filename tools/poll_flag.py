"""Poll single flag to verify stability within state."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

ADDR = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x0106C9FC

with PineClient() as pc:
    last = None
    flips = 0
    samples = 0
    t0 = time.monotonic()
    DUR = 3.0
    while time.monotonic() - t0 < DUR:
        v = pc.read_u32(ADDR)
        samples += 1
        if last is not None and v != last:
            flips += 1
        last = v

    print(f"[*] addr 0x{ADDR:08X}  {samples} samples in {DUR:.1f}s  last value=0x{v:08X}  flips={flips}")
