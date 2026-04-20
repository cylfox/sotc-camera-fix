"""Locate the camera controller's basis block in the current session.

Per docs/camera_struct/sotc_camera_struct.md:
  - Outer host object has type byte 0x0A at offset +0x08
  - Controller = host + 0x20
  - basis_a lives at controller + 0x570 (0x60 bytes: forward/pad/up/pad/right/pad/pos/pad/ ...)
  - Each unit vector has magnitude ~1.0 and they're orthogonal

Session anchors drift between runs. Strategy:
  1. First try the research-doc session addresses (0x01C18080 / 0x01C180A0).
  2. If those don't look right, scan a heap window for orthonormal vectors:
     words w0..w3 where (w0,w1,w2) form a unit vector (magnitude ~ 1.0).

Usage:
    py find_camera_basis.py
    py find_camera_basis.py --scan 0x01C00000 --size 0x00200000
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pine_client import PineClient


def read_vec3(pc: PineClient, addr: int) -> tuple[float, float, float]:
    return (pc.read_f32(addr), pc.read_f32(addr + 4), pc.read_f32(addr + 8))


def mag(v):
    return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)


def dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def check_basis(pc: PineClient, controller_addr: int, verbose=True) -> bool:
    """Read the basis at controller+0x570 and check it's orthonormal."""
    b = controller_addr + 0x570
    try:
        fwd = read_vec3(pc, b + 0x00)
        up  = read_vec3(pc, b + 0x10)
        rgt = read_vec3(pc, b + 0x20)
        pos = read_vec3(pc, b + 0x30)
    except Exception as e:
        if verbose:
            print(f"    read error: {e}")
        return False

    m_fwd = mag(fwd); m_up = mag(up); m_rgt = mag(rgt)
    d_fu = dot(fwd, up); d_fr = dot(fwd, rgt); d_ur = dot(up, rgt)

    # Must be unit vectors and orthogonal
    ok = (
        abs(m_fwd - 1.0) < 1e-3
        and abs(m_up - 1.0) < 1e-3
        and abs(m_rgt - 1.0) < 1e-3
        and abs(d_fu) < 1e-2
        and abs(d_fr) < 1e-2
        and abs(d_ur) < 1e-2
    )

    if verbose:
        print(f"  controller=0x{controller_addr:08X}  basis_a=0x{b:08X}")
        print(f"    forward={fwd}  |v|={m_fwd:.5f}")
        print(f"    up     ={up}   |v|={m_up:.5f}")
        print(f"    right  ={rgt}  |v|={m_rgt:.5f}")
        print(f"    pos    ={pos}")
        print(f"    dots: fwd.up={d_fu:+.4f}  fwd.rgt={d_fr:+.4f}  up.rgt={d_ur:+.4f}")
        print(f"    orthonormal? {ok}")
    return ok


def try_research_anchor(pc: PineClient) -> int | None:
    """Try the exact session addresses from the research doc."""
    host = 0x01C18080
    controller = 0x01C180A0
    print(f"[*] Trying research-doc addresses: host=0x{host:08X}, controller=0x{controller:08X}")
    try:
        type_byte = pc.read_u8(host + 8)
    except Exception as e:
        print(f"    host read failed: {e}")
        return None
    print(f"    host[+8] = 0x{type_byte:02X} (research expected 0x0A)")
    if check_basis(pc, controller, verbose=True):
        return controller
    return None


def scan_for_basis(pc: PineClient, base: int, size: int) -> list[int]:
    """Scan a range looking for controller candidates.
    Heuristic: at some aligned offset, the basis block (forward vec3)
    is a unit vector AND up vec3 is a unit vector AND fwd.up ~ 0.
    This should pin down real basis blocks.
    """
    print(f"[*] Scanning 0x{base:08X}..0x{base+size:08X} ({size // (1024*1024)} MB)")
    print(f"    Looking for controller+0x570 that passes the orthonormal check.")
    hits = []
    # Heap quadword alignment = 0x10
    # The 0x570 offset is quadword aligned, and basis block starts at a qw boundary.
    step = 0x10
    # Read in chunks to be gentler on PINE
    for addr in range(base, base + size, step):
        if (addr - base) % (1024 * 64) == 0:
            print(f"    progress: 0x{addr:08X}")
        try:
            # Cheap check: magnitude of first vec3 near 1.0
            x = pc.read_f32(addr)
            y = pc.read_f32(addr + 4)
            z = pc.read_f32(addr + 8)
            m = math.sqrt(x*x + y*y + z*z)
            if abs(m - 1.0) > 1e-3:
                continue
            # Also check the up vector at +0x10
            ux = pc.read_f32(addr + 0x10)
            uy = pc.read_f32(addr + 0x14)
            uz = pc.read_f32(addr + 0x18)
            um = math.sqrt(ux*ux + uy*uy + uz*uz)
            if abs(um - 1.0) > 1e-3:
                continue
            # Must be orthogonal
            d = x*ux + y*uy + z*uz
            if abs(d) > 1e-2:
                continue
        except Exception:
            continue
        # This addr is a candidate basis block. Controller = addr - 0x570.
        controller = addr - 0x570
        print(f"  candidate basis at 0x{addr:08X}, controller would be 0x{controller:08X}")
        hits.append(controller)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true",
                    help="force scan even if research anchor works")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x01C00000,
                    help="scan base")
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x00200000,
                    help="scan size")
    args = ap.parse_args()

    with PineClient() as pc:
        if not args.scan:
            controller = try_research_anchor(pc)
            if controller is not None:
                print(f"[*] FOUND controller at 0x{controller:08X} via research anchor")
                return 0
            print("[*] Research anchor did not validate; falling back to scan")

        hits = scan_for_basis(pc, args.base, args.size)
        print(f"[*] Scan found {len(hits)} candidate(s)")
        for h in hits:
            print(f"    controller = 0x{h:08X}")
            check_basis(pc, h, verbose=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
