"""Determine whether aim-mode left-stick input writes through 0x0106C230
(the triple-buffer we just proved is the lever).

Procedure:
  1. Hammer (+1.0, 0.0, 0.0) into the buffer chain for 3 seconds.
  2. User pushes left stick left/right during this.
  3. We poll 0x0106C230 between hammer bursts to see if the user's
     input is perturbing it (if so, aim control uses this path).
"""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

BUFFERS = [0x0106C230, 0x0106C1F0, 0x0106C1B0]

TX = struct.unpack('<I', struct.pack('<f', +1.0))[0]
TY = struct.unpack('<I', struct.pack('<f',  0.0))[0]
TZ = struct.unpack('<I', struct.pack('<f',  0.0))[0]

DUR = 5.0

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

with PineClient() as pc:
    print("[*] Starting — push left stick LEFT and RIGHT during the next 5s.")
    print("    Hammering (+1.0, 0.0, 0.0) into the buffer chain and polling.")
    print()
    t0 = time.monotonic()
    writes = 0
    # We hammer in bursts of ~50 writes, then poll to see if the game
    # has perturbed the value since our last write.
    perturbations = 0
    while time.monotonic() - t0 < DUR:
        # Hammer burst
        for _ in range(30):
            for a in BUFFERS:
                pc.write_u32(a+0, TX)
                pc.write_u32(a+4, TY)
                pc.write_u32(a+8, TZ)
                writes += 3
        # Poll
        vx = pc.read_u32(BUFFERS[0]+0)
        vy = pc.read_u32(BUFFERS[0]+4)
        vz = pc.read_u32(BUFFERS[0]+8)
        if vx != TX or vy != TY or vz != TZ:
            perturbations += 1
            print(f"    t={time.monotonic()-t0:.2f}s  PERTURBED: "
                  f"({asf(vx):+.4f}, {asf(vy):+.4f}, {asf(vz):+.4f})")
    print(f"\n[*] {writes} writes, {perturbations} observed perturbations")
    if perturbations == 0:
        print("    -> game did NOT perturb the buffer. Left-stick aim may use a")
        print("       different path, or hammer rate is too high to detect.")
    else:
        print("    -> game WAS writing to the buffer between our hammer bursts.")
        print("       left-stick aim likely flows through this buffer.")
