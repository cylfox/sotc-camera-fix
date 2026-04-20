"""Watch the camera basis block at controller+0x570 live.

Run while playing. Moves in the FORWARD vector tell us the camera is
rotating. We want to confirm: does left-stick-X in aim mode rotate this
basis? (If yes -> it's the right target. If no -> aim uses a different
camera path.)

Usage: py watch_basis.py [duration_s]
"""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CONTROLLER = 0x01C180A0
BASIS_A = CONTROLLER + 0x570

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0


def read_vec3(pc, addr):
    return (pc.read_f32(addr), pc.read_f32(addr + 4), pc.read_f32(addr + 8))


def mag(v): return (v[0]**2 + v[1]**2 + v[2]**2) ** 0.5


with PineClient() as pc:
    print(f"[*] watching basis at 0x{BASIS_A:08X} for {DUR:.1f}s")
    print(f"    forward = vec3 @ 0x{BASIS_A+0x00:08X}")
    print(f"    up      = vec3 @ 0x{BASIS_A+0x10:08X}")
    print(f"    right   = vec3 @ 0x{BASIS_A+0x20:08X}")
    print()
    t0 = time.monotonic()
    samples = 0
    last_fwd = None
    changes_fwd = 0
    while time.monotonic() - t0 < DUR:
        fwd = read_vec3(pc, BASIS_A + 0x00)
        up  = read_vec3(pc, BASIS_A + 0x10)
        rgt = read_vec3(pc, BASIS_A + 0x20)
        samples += 1
        if last_fwd is not None and fwd != last_fwd:
            changes_fwd += 1
        last_fwd = fwd
        if samples % 3 == 0:
            print(f"  t={time.monotonic()-t0:5.2f}s  fwd=({fwd[0]:+.4f}, {fwd[1]:+.4f}, {fwd[2]:+.4f})")
        time.sleep(0.1)
    print(f"\n[*] {samples} samples, fwd changes: {changes_fwd}")
