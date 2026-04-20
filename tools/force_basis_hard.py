"""Diagnostic: force basis to a HARD, FIXED direction for 5 seconds.

If the camera view jumps to face +X (forward=(1,0,0)), our writes dominate
the game -> basis is the real camera, reticle drift is another bug.

If the camera keeps doing whatever vanilla aim does -> the game is
overwriting us, or basis isn't the real camera.
"""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

BASIS_A_FWD  = 0x01C18610
BASIS_B_FWD  = 0x01C18670


def f32(x): return struct.unpack("<I", struct.pack("<f", x))[0]


def write_basis(pc, base, fwd, up, rgt):
    # forward
    pc.write_u32(base + 0x00, f32(fwd[0]))
    pc.write_u32(base + 0x04, f32(fwd[1]))
    pc.write_u32(base + 0x08, f32(fwd[2]))
    # up
    pc.write_u32(base + 0x10, f32(up[0]))
    pc.write_u32(base + 0x14, f32(up[1]))
    pc.write_u32(base + 0x18, f32(up[2]))
    # right
    pc.write_u32(base + 0x20, f32(rgt[0]))
    pc.write_u32(base + 0x24, f32(rgt[1]))
    pc.write_u32(base + 0x28, f32(rgt[2]))


# Hardcoded: camera looks along +X (east), up = +Y, right = -Z (right-handed).
FWD = (1.0, 0.0, 0.0)
UP  = (0.0, 1.0, 0.0)
RGT = (0.0, 0.0, -1.0)

DUR = 5.0

with PineClient() as pc:
    print(f"[*] Forcing basis to HARD +X direction for {DUR:.1f}s")
    print(f"    Get in aim mode; watch if camera faces east relentlessly.")
    t0 = time.monotonic()
    writes = 0
    while time.monotonic() - t0 < DUR:
        write_basis(pc, BASIS_A_FWD, FWD, UP, RGT)
        write_basis(pc, BASIS_B_FWD, FWD, UP, RGT)
        writes += 1
        # No sleep -- as fast as possible
    elapsed = time.monotonic() - t0
    print(f"[*] {writes} write cycles in {elapsed:.2f}s ({writes/elapsed:.0f} Hz)")

    # Immediate read back
    print("[*] Immediate read of basis_a.forward after stopping:")
    fx = pc.read_f32(BASIS_A_FWD)
    fy = pc.read_f32(BASIS_A_FWD + 4)
    fz = pc.read_f32(BASIS_A_FWD + 8)
    print(f"    ({fx:+.4f}, {fy:+.4f}, {fz:+.4f})")
    if abs(fx - 1.0) < 0.01 and abs(fy) < 0.01 and abs(fz) < 0.01:
        print("    Our write STUCK - game didn't overwrite in the gap.")
    else:
        print("    Our write was OVERWRITTEN by the game.")
