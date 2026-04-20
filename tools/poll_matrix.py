"""Poll the candidate camera rotation matrix to see if it tracks live."""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

BASE = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x015E7A80
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

with PineClient() as pc:
    print(f"[*] Polling 3x4 matrix at 0x{BASE:08X} for {DUR}s. Rotate the camera.\n")
    t0 = time.monotonic()
    last_key = None
    while time.monotonic() - t0 < DUR:
        vals = [pc.read_u32(BASE + i*4) for i in range(12)]
        key = tuple(vals)
        if key != last_key:
            t = time.monotonic() - t0
            # Display as 3x4 matrix
            print(f"t={t:5.2f}s")
            for row in range(3):
                print(f"  ({asf(vals[row*4+0]):+.3f}, {asf(vals[row*4+1]):+.3f}, "
                      f"{asf(vals[row*4+2]):+.3f}, {asf(vals[row*4+3]):+.3f})")
            last_key = key
        time.sleep(0.1)
