"""Hammer test: continuously write IDENTITY basis into the candidate
aim-camera matrix at 0x01C18A80..0x01C18AB0 for 5 seconds while user is
in aim mode. If the camera visibly changes, this matrix IS a live input
and we have a patch lever. If nothing changes, it's a read-only output.

Origin at 0x01C18AB0 is left unchanged (we don't want to teleport the
camera to world origin).

Runs for 5s. Exit aim mode to recover from any visual glitching.
"""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

BASE = 0x01C18A80

def f32(f):
    return struct.unpack('<I', struct.pack('<f', f))[0]

# Identity basis (leave origin untouched)
IDENTITY_BASIS = [
    # Row 0 at +0x00 (x axis)
    (BASE + 0x00, f32(1.0)),
    (BASE + 0x04, f32(0.0)),
    (BASE + 0x08, f32(0.0)),
    # Row 1 at +0x10 (y axis)
    (BASE + 0x10, f32(0.0)),
    (BASE + 0x14, f32(1.0)),
    (BASE + 0x18, f32(0.0)),
    # Row 2 at +0x20 (z axis)
    (BASE + 0x20, f32(0.0)),
    (BASE + 0x24, f32(0.0)),
    (BASE + 0x28, f32(1.0)),
]

DUR = 5.0

def main():
    with PineClient() as pc:
        # Baseline
        print("[*] Baseline (first frame):")
        for off in (0x00, 0x10, 0x20, 0x30):
            x, y, z = (struct.unpack('<f', struct.pack('<I', pc.read_u32(BASE + off + 4*i)))[0] for i in range(3))
            print(f"    0x{BASE+off:08X}  ({x:+.3f}, {y:+.3f}, {z:+.3f})")
        print()
        print(f"[*] Hammering identity basis into 0x{BASE:08X}..+0x30 (leaving origin untouched) for {DUR:.0f}s...")
        print("    Watch the camera — does it rotate/glitch?")
        t0 = time.monotonic()
        writes = 0
        while time.monotonic() - t0 < DUR:
            for addr, val in IDENTITY_BASIS:
                pc.write_u32(addr, val)
                writes += 1
        print(f"[*] {writes} writes in {DUR:.1f}s ({writes/DUR:.0f}/s)")

        # Check final state immediately
        print("\n[*] Immediately after hammer stop:")
        for off in (0x00, 0x10, 0x20, 0x30):
            x, y, z = (struct.unpack('<f', struct.pack('<I', pc.read_u32(BASE + off + 4*i)))[0] for i in range(3))
            print(f"    0x{BASE+off:08X}  ({x:+.3f}, {y:+.3f}, {z:+.3f})")

if __name__ == "__main__":
    main()
