"""Watch a 32-bit float at a given address, printing it live at ~20 Hz.

Usage: py watch_f32.py 0x0106DF00 [duration_s]
"""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

ADDR = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x0106DF00
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0

with PineClient() as pc:
    t0 = time.monotonic()
    last = None
    flips = 0
    samples = 0
    vmin = None; vmax = None
    print(f"[*] watching 0x{ADDR:08X} as float for {DUR:.1f}s ...")
    while time.monotonic() - t0 < DUR:
        u = pc.read_u32(ADDR)
        f = struct.unpack("<f", struct.pack("<I", u))[0]
        samples += 1
        if last is not None and u != last:
            flips += 1
        if vmin is None or f < vmin: vmin = f
        if vmax is None or f > vmax: vmax = f
        # Print once per ~100 ms so the stream is readable
        if samples % 2 == 0:
            print(f"  t={time.monotonic()-t0:5.2f}s  f32={f:+.5f}  u32=0x{u:08X}")
        last = u
        time.sleep(0.05)
    print(f"[*] {samples} samples, {flips} flips, range [{vmin:+.5f}, {vmax:+.5f}]")
