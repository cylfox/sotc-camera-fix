"""Pad-level stick remap for aim mode.

In aim mode (mode flag 0x0106C9FC == 0), copy LEFT stick X into RIGHT
stick X in each pad buffer. The camera's right-stick-X input is driven
by the user's left-stick X motion, so panning the camera via left stick
works alongside the existing aim-center hook.

Pad buffers found by range-scan while user wiggled sticks:
  Buffer 1: 0x0013A55E (rX), 0x0013A560 (lX)
  Buffer 2: 0x0013A5DE (rX), 0x0013A5E0 (lX)
  Buffer 3: 0x0013A646 (rX), 0x0013A648 (lX)

Note: this is a LIVE SCRIPT (not a pnach). Run while playing.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

MODE_FLAG = 0x0106C9FC

# (right_x_addr, left_x_addr) pairs — one per buffer
PAIRS = [
    (0x0013A55E, 0x0013A560),
    (0x0013A5DE, 0x0013A5E0),
    (0x0013A646, 0x0013A648),
]

with PineClient() as pc:
    print(f"[*] Aim stick remap running. Ctrl+C to stop.")
    print(f"    In aim mode: left-stick X will be copied into right-stick X.")
    print(f"    Combined with aim-center hook: left stick yaw pans camera.")
    try:
        while True:
            mode = pc.read_u32(MODE_FLAG)
            if mode == 0:   # aim mode
                for rx, lx in PAIRS:
                    lx_val = pc.read_u8(lx)
                    pc.write_u8(rx, lx_val)
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
