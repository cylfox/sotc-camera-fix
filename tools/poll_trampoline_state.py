"""Poll the v2 trampoline's scratch memory to verify it's operating
correctly. Run during free-roam and aim to see:
  - saved_x/y/z being captured from 0x0106C230 during free-roam
  - counter being reset to 30 during free-roam, decrementing in aim
  - mode flag transitions
"""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

SAVED_X = 0x001A4A10
SAVED_Y = 0x001A4A14
SAVED_Z = 0x001A4A18
COUNTER = 0x001A4A1C
MODE    = 0x0106C9FC
BUFFER  = 0x0106C230  # current direction

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

DUR = 10.0
with PineClient() as pc:
    print(f"[*] Polling trampoline state for {DUR:.0f}s. Switch between free-roam/aim.")
    print(f"    cols: mode | counter | saved  | current_direction")
    t0 = time.monotonic()
    last = None
    while time.monotonic() - t0 < DUR:
        mode = pc.read_u32(MODE)
        cnt  = pc.read_u32(COUNTER)
        sx = asf(pc.read_u32(SAVED_X))
        sy = asf(pc.read_u32(SAVED_Y))
        sz = asf(pc.read_u32(SAVED_Z))
        bx = asf(pc.read_u32(BUFFER + 0))
        by = asf(pc.read_u32(BUFFER + 4))
        bz = asf(pc.read_u32(BUFFER + 8))
        row = (mode, cnt, round(sx,3), round(sy,3), round(sz,3), round(bx,3), round(by,3), round(bz,3))
        if row != last:
            t = time.monotonic() - t0
            print(f"  t={t:5.2f}s  mode={mode}  cnt={cnt:3d}  saved=({sx:+.3f},{sy:+.3f},{sz:+.3f})  current=({bx:+.3f},{by:+.3f},{bz:+.3f})")
            last = row
        time.sleep(0.05)
