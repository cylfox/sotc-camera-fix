"""Definitive test: does writing to 0x0106C230 actually propagate to the
rendered camera forward at 0x0106E7C0?

Hammers 0x0106C230 (and friends in the triple buffer) with a dramatically
different unit vector, while simultaneously polling 0x0106E7C0 to see if
the rendered forward follows.

Writes: (+1.0, 0.0, 0.0)  — a clean "look straight +X" direction
Polls:  0x0106E7C0 at the end of each hammer burst

If 0x0106E7C0 becomes (~+1.0, 0.0, 0.0), the chain works and hammer is
a valid lever. If 0x0106E7C0 stays at its aim-default, the renderer is
reading from elsewhere.
"""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

BUFFERS = [0x0106C230, 0x0106C1F0, 0x0106C1B0]
OUTPUT  = 0x0106E7C0

TARGET_X = struct.unpack('<I', struct.pack('<f', +1.0))[0]
TARGET_Y = struct.unpack('<I', struct.pack('<f',  0.0))[0]
TARGET_Z = struct.unpack('<I', struct.pack('<f',  0.0))[0]

DUR = 5.0

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

def main():
    with PineClient() as pc:
        # Baseline
        print("[*] BEFORE hammer — current state:")
        for a in BUFFERS + [OUTPUT]:
            x = pc.read_u32(a); y = pc.read_u32(a+4); z = pc.read_u32(a+8)
            print(f"    0x{a:08X}  ({asf(x):+.4f}, {asf(y):+.4f}, {asf(z):+.4f})")

        print(f"\n[*] Hammering (+1.0, 0.0, 0.0) into the 3 buffers for {DUR:.0f}s...")
        print("    Simultaneously polling 0x0106E7C0 every ~100ms to see if it follows.")
        print("    You should watch the camera on screen — does it snap?")
        t0 = time.monotonic()
        writes = 0
        next_report = t0 + 0.5
        while time.monotonic() - t0 < DUR:
            for a in BUFFERS:
                pc.write_u32(a+0, TARGET_X)
                pc.write_u32(a+4, TARGET_Y)
                pc.write_u32(a+8, TARGET_Z)
                writes += 3
            if time.monotonic() > next_report:
                next_report += 0.5
                x = pc.read_u32(OUTPUT); y = pc.read_u32(OUTPUT+4); z = pc.read_u32(OUTPUT+8)
                mag = (asf(x)**2 + asf(y)**2 + asf(z)**2)**0.5
                print(f"    t={time.monotonic()-t0:.1f}s  0x{OUTPUT:08X} = "
                      f"({asf(x):+.4f}, {asf(y):+.4f}, {asf(z):+.4f})  |v|={mag:.3f}")

        print(f"\n[*] {writes} writes in {DUR:.1f}s ({writes/DUR:.0f}/s)")

        print("\n[*] AFTER hammer stop — post-state (should snap back):")
        time.sleep(0.2)
        for a in BUFFERS + [OUTPUT]:
            x = pc.read_u32(a); y = pc.read_u32(a+4); z = pc.read_u32(a+8)
            print(f"    0x{a:08X}  ({asf(x):+.4f}, {asf(y):+.4f}, {asf(z):+.4f})")

if __name__ == "__main__":
    main()
