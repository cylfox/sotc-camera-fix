"""Scan for stick bytes."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

RANGE_START = 0x00130000
RANGE_END   = 0x00140000
DUR = 10.0

with PineClient() as pc:
    print(f"[*] Scanning for {DUR:.0f}s. Move ONLY the specified axis.")
    t0 = time.monotonic()
    initial = pc.read_bytes(RANGE_START, RANGE_END - RANGE_START)
    mins = bytearray(initial)
    maxs = bytearray(initial)
    while time.monotonic() - t0 < DUR:
        chunk = pc.read_bytes(RANGE_START, RANGE_END - RANGE_START)
        for i in range(len(chunk)):
            if chunk[i] < mins[i]: mins[i] = chunk[i]
            if chunk[i] > maxs[i]: maxs[i] = chunk[i]
    print(f"\n    Bytes with range > 60:")
    for i in range(len(mins)):
        r = maxs[i] - mins[i]
        if r > 60:
            print(f"      0x{RANGE_START+i:08X}  min=0x{mins[i]:02X}  max=0x{maxs[i]:02X}  range={r}")
