"""Guided diff of the controller struct. Prompts you what to do when.

Flow:
  1. "STILL PHASE" - 3s countdown, hands off controller. Snapshot A.
  2. "ACTION PHASE" - 5s. DO THIS: walk forward (left stick up) AND rotate
     right stick continuously. This exercises both position and camera yaw.
  3. Snapshot B. Diff. Print offsets that changed.

If nothing changes, the struct at 0x01C180A0 is dormant and we're on the
wrong anchor.
"""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CONTROLLER = 0x01C180A0
SIZE = 0x800


def snap(pc, base, size):
    out = bytearray(size)
    for off in range(0, size, 8):
        q = pc.read_u64(base + off)
        out[off:off+8] = q.to_bytes(8, 'little')
    return bytes(out)


def classify(w: int) -> str:
    f = struct.unpack("<f", struct.pack("<I", w))[0]
    if w == 0:
        return "zero"
    if 0x00100000 <= w <= 0x02000000:
        return f"ptr(0x{w:08X})"
    exp = (w >> 23) & 0xFF
    if 0x60 <= exp <= 0x99:
        return f"f32={f:+.4f}"
    return f"u32(0x{w:08X})"


def countdown(secs, msg):
    for i in range(secs, 0, -1):
        print(f"  {msg} ... {i}", flush=True)
        time.sleep(1)


with PineClient() as pc:
    print("=" * 60)
    print("PHASE 1: STILL. Hands off the controller. 3s countdown.")
    print("=" * 60)
    countdown(3, "hands off")
    print("[*] Snapshot A (takes ~1s)")
    snap_a = snap(pc, CONTROLLER, SIZE)
    print()

    print("=" * 60)
    print("PHASE 2: ACTION! For the next 5 seconds:")
    print("  - Push LEFT STICK UP (walk forward)")
    print("  - AND rotate RIGHT STICK in circles")
    print("=" * 60)
    countdown(5, "ACTION - walk + right stick")
    print("[*] Snapshot B (takes ~1s)")
    snap_b = snap(pc, CONTROLLER, SIZE)
    print()

# Diff
changes = []
for off in range(0, SIZE, 4):
    a = int.from_bytes(snap_a[off:off+4], 'little')
    b = int.from_bytes(snap_b[off:off+4], 'little')
    if a != b:
        changes.append((off, a, b))

print(f"[*] {len(changes)} words changed out of {SIZE // 4}")
print()
if not changes:
    print("NOTHING CHANGED. This controller struct is dormant.")
    print("Next step: scan for a DIFFERENT controller that responds to input.")
else:
    print(f"{'offset':>8}  {'before':<22}  {'after':<22}")
    for off, a, b in changes:
        abs_addr = CONTROLLER + off
        print(f"  +0x{off:03X} (0x{abs_addr:08X})  {classify(a):<22}  {classify(b):<22}")
