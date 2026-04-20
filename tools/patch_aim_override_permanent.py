"""Live tweak: change the aim-override to NEVER decrement counter.
This makes the override permanent while in aim mode (counter never hits 0).

We replace the decrement instruction at 0x001A49F0 with a nop.
Also we replace the counter-load-and-check with: always go straight to override.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

with PineClient() as pc:
    print("Swapping 'addiu t5, t5, -1' with 'addiu t5, zero, 30' (counter never drops)")
    # Replace addiu t5, t5, -1 (0x25ADFFFF) at 0x001A49F0 with addiu t5, zero, 30 (0x240D001E)
    pc.write_u32(0x001A49F0, 0x240D001E)
    v = pc.read_u32(0x001A49F0)
    print(f"  0x001A49F0 = 0x{v:08X}  (expect 0x240D001E)")
    print("Counter now stays at 30 forever during aim mode. Test aim with left stick.")
