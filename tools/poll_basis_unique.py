"""Poll basis forward at high rate, print only when it changes.

Lets us confirm the struct is alive or dormant. Play normally for 10s
(walk, rotate camera, enter/leave aim mode) and see if anything moves.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CONTROLLER = 0x01C180A0
BASIS_A = CONTROLLER + 0x570
BASIS_B = CONTROLLER + 0x5D0
DUR = 10.0


def read_vec3(pc, addr):
    return (pc.read_f32(addr), pc.read_f32(addr + 4), pc.read_f32(addr + 8))


with PineClient() as pc:
    print(f"[*] Polling basis_a.forward and basis_b.forward for {DUR:.1f}s")
    print(f"[*] DO ANYTHING: walk, rotate camera, enter aim mode, move sticks")
    t0 = time.monotonic()
    last_a = None
    last_b = None
    changes_a = 0
    changes_b = 0
    samples = 0
    while time.monotonic() - t0 < DUR:
        fa = read_vec3(pc, BASIS_A + 0x00)
        fb = read_vec3(pc, BASIS_B + 0x00)
        samples += 1
        if last_a is None or fa != last_a:
            changes_a += 1
            print(f"  t={time.monotonic()-t0:5.2f}s  basis_a.fwd=({fa[0]:+.4f}, {fa[1]:+.4f}, {fa[2]:+.4f})")
        if last_b is None or fb != last_b:
            changes_b += 1
            print(f"  t={time.monotonic()-t0:5.2f}s  basis_b.fwd=({fb[0]:+.4f}, {fb[1]:+.4f}, {fb[2]:+.4f})")
        last_a = fa
        last_b = fb
        time.sleep(0.03)

    print(f"\n[*] {samples} samples")
    print(f"    basis_a changes: {changes_a}")
    print(f"    basis_b changes: {changes_b}")
