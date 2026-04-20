"""Dump raw words at an address for sanity checking.

Usage: py raw_dump.py 0x013B7FB8 [count]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

addr = int(sys.argv[1], 0)
count = int(sys.argv[2]) if len(sys.argv) > 2 else 16

with PineClient() as pc:
    for i in range(count):
        a = addr + 4 * i
        w = pc.read_u32(a)
        b = w.to_bytes(4, 'little')
        print(f"  0x{a:08X}  word=0x{w:08X}  bytes={b.hex(' ')}")
