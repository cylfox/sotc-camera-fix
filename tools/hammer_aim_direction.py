"""Continuously write a target direction vector into the level-1 direction
buffer at 0x0106C230. If the camera rotates in response, this is a viable
patch point. If the camera ignores it (game overwrites every frame), we
need to find the upstream writer instead.

Target direction used: the free-roam value we captured at the start of
the investigation: (-0.9641, +0.0766, +0.2541).

Run for 10 seconds. Also hammers the other two history buffers
(0x0106C1F0, 0x0106C1B0) in case the chain matters.
"""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TARGETS = [0x0106C230, 0x0106C1F0, 0x0106C1B0]

# Free-roam direction we captured earlier
DIR_X = 0xBF76D1F5  # -0.9641
DIR_Y = 0x3D9CEC39  # +0.0766
DIR_Z = 0x3E8217DF  # +0.2541

DUR = 10.0

def main():
    with PineClient() as pc:
        print(f"[*] Hammering {len(TARGETS)} buffers with (-0.9641, +0.0766, +0.2541) for {DUR:.0f}s")
        print("    Watch the camera — does it rotate back toward the free-roam direction?")
        t0 = time.monotonic()
        writes = 0
        while time.monotonic() - t0 < DUR:
            for addr in TARGETS:
                pc.write_u32(addr + 0, DIR_X)
                pc.write_u32(addr + 4, DIR_Y)
                pc.write_u32(addr + 8, DIR_Z)
                writes += 3
        print(f"[*] {writes} u32 writes in {DUR:.1f}s ({writes/DUR:.0f}/s)")

if __name__ == "__main__":
    main()
