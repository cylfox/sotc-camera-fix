"""Proof-of-concept: in aim mode, force basis_a.forward to aim-yaw direction.

Requires the v9 mirror hook to be applied (so 0x0106DF00 holds live aim-yaw).

Loop at ~120 Hz:
  - read mode flag 0x0106C9FC (1=free-roam, 0=aim)
  - if aim mode:
      yaw = f32 @ 0x0106DF00
      forward = (cos yaw, 0, sin yaw)   [will swap if axis convention wrong]
      write basis_a.forward @ 0x01C18610..0x01C18618
      (leave up/right untouched for now -- first pass test)

If the camera view rotates following left-X in aim mode, the concept works.
Ctrl+C to stop.
"""
import os, sys, time, math, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

MODE_FLAG    = 0x0106C9FC
AIM_YAW      = 0x0106DF00
BASIS_A_FWD  = 0x01C18610       # controller+0x570 "target" basis
BASIS_B_FWD  = 0x01C18670       # controller+0x5D0 "current" basis (smoothed)


def f32_bits(f):
    return struct.unpack("<I", struct.pack("<f", f))[0]


def write_fwd(pc, addr, fx, fy, fz):
    pc.write_u32(addr + 0, f32_bits(fx))
    pc.write_u32(addr + 4, f32_bits(fy))
    pc.write_u32(addr + 8, f32_bits(fz))


def write_full_basis_yaw(pc, base, yaw):
    """Write consistent yaw-only basis at base. Forward/up/right as a
    proper Y-axis rotation. Leaves position (+0x30) alone."""
    import math
    c = math.cos(yaw); s = math.sin(yaw)
    # forward = (c, 0, s)
    pc.write_u32(base + 0x00, f32_bits(c))
    pc.write_u32(base + 0x04, f32_bits(0.0))
    pc.write_u32(base + 0x08, f32_bits(s))
    # up = (0, 1, 0)
    pc.write_u32(base + 0x10, f32_bits(0.0))
    pc.write_u32(base + 0x14, f32_bits(1.0))
    pc.write_u32(base + 0x18, f32_bits(0.0))
    # right = (-s, 0, c)   (right-handed: right = up x forward)
    pc.write_u32(base + 0x20, f32_bits(-s))
    pc.write_u32(base + 0x24, f32_bits(0.0))
    pc.write_u32(base + 0x28, f32_bits(c))


# Two axis-convention hypotheses: try (cos,0,sin) first; swap to (sin,0,cos) if camera rotates backwards.
CONVENTION = os.environ.get("CONV", "cos_sin")  # cos_sin | sin_cos


with PineClient() as pc:
    print(f"[*] Forcing basis_a.forward in aim mode, convention={CONVENTION}")
    print(f"    Move LEFT STICK X in aim mode. Watch if camera rotates.")
    DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    print(f"    Running for {DUR:.1f}s...")
    writes = 0
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < DUR:
            mode = pc.read_u32(MODE_FLAG)
            if mode == 0:  # aim
                yaw = pc.read_f32(AIM_YAW)
                c, s = math.cos(yaw), math.sin(yaw)
                # Write full consistent basis (fwd+up+right) to both a and b
                write_full_basis_yaw(pc, BASIS_A_FWD, yaw)
                write_full_basis_yaw(pc, BASIS_B_FWD, yaw)
                writes += 1
                if writes % 30 == 0:
                    print(f"  yaw={yaw:+.4f}  fwd=({c:+.3f}, 0, {s:+.3f})  [{writes} writes]")
            time.sleep(1.0 / 120)
    except KeyboardInterrupt:
        print(f"\n[*] Stopped. {writes} basis writes made.")
