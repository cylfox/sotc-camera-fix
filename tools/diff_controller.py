"""Diff the camera controller struct before/after stick input.

Surfaces every 4-byte word that changed between two snapshots.
Filters for float-like values in the unit-vector / angle ranges so
we can spot rotational state quickly.

Timeline:
  - 3s "HOLD STILL"  — take snapshot A
  - 5s "MOVE THE STICK YOU CARE ABOUT" — snapshot B taken at end
  - diff & print.
"""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CONTROLLER = 0x01C180A0
SIZE = 0x800


def snap(pc, base, size):
    out = bytearray(size)
    for off in range(0, size, 4):
        w = pc.read_u32(base + off)
        out[off:off+4] = w.to_bytes(4, 'little')
    return bytes(out)


def classify(w: int) -> str:
    f = struct.unpack("<f", struct.pack("<I", w))[0]
    if w == 0:
        return "zero"
    if 0x00100000 <= w <= 0x02000000:
        return f"ptr(0x{w:08X})"
    exp = (w >> 23) & 0xFF
    if 0x68 <= exp <= 0x90:  # float ~1e-7 .. ~2e5
        return f"f32={f:+.5f}"
    return f"u32(0x{w:08X})"


def main():
    with PineClient() as pc:
        print("[*] STILL — hold stick neutral. 3s.")
        time.sleep(3)
        print("[*] Taking snapshot A")
        snap_a = snap(pc, CONTROLLER, SIZE)
        print("[*] NOW MOVE THE STICK you want to test, for 5s")
        time.sleep(5)
        print("[*] Taking snapshot B")
        snap_b = snap(pc, CONTROLLER, SIZE)

    changes = []
    for off in range(0, SIZE, 4):
        a = int.from_bytes(snap_a[off:off+4], 'little')
        b = int.from_bytes(snap_b[off:off+4], 'little')
        if a != b:
            changes.append((off, a, b))

    print(f"\n[*] {len(changes)} words changed")
    print(f"{'offset':>8}  {'before':<22}  {'after':<22}")
    for off, a, b in changes:
        print(f"  +0x{off:03X}    {classify(a):<22}  {classify(b):<22}")


if __name__ == "__main__":
    main()
