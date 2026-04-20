"""v8: strip the aim-mode stick remap from trampoline A.

Converts a running v7 patch into v8:
  - Trampoline A at 0x001A4984 becomes the v1 (11-instruction) shape:
    autofocus disable in free-roam, aim mode passes the byte through.
  - The 4 words 0x001A49B0..0x001A49BC (which held remap instructions
    in v7) are zeroed so nothing stale lives in the code region.
  - Hook A (0x001ACD44/48) and Hook B + Trampoline B (0x01176AB4,
    0x001A5248..0x001A5264) are left alone -- they don't change
    between v7 and v8.

Post-conditions:
  - Autofocus: still disabled in free-roam.
  - Aim mode: reticle still centered (Hook B unchanged).
  - Aim mode: left-stick X NO LONGER yaws the camera (the remap is gone).
    This is the starting point for investigating a cleaner aim-yaw fix.

Restore v7 by running `apply_combined_v7.py` again (it rewrites the
region fully).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984

PATCHES = [
    # v1 trampoline A body (11 instructions)
    (TRAMP + 0x00, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x04, 0x8C21C9FC, "lw at, -0x3604(at)          ; mode flag"),
    (TRAMP + 0x08, 0x10200006, "beq at, zero, +6            ; aim -> skip to ret"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    (TRAMP + 0x10, 0x2441FFBF, "addiu at, v0, -0x41"),
    (TRAMP + 0x14, 0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0x18, 0x10200002, "beq at, zero, +2            ; outside deadzone -> ret"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0x240200C0, "addiu v0, zero, 0xC0"),
    (TRAMP + 0x24, 0x0806B353, "j 0x001ACD4C"),
    (TRAMP + 0x28, 0xA2020057, "sb v0, 0x57(s0)             [jump delay]"),
    # Zero the 4 words that v7 used for the aim-mode remap tail.
    (TRAMP + 0x2C, 0x00000000, "(was v7 remap) zero"),
    (TRAMP + 0x30, 0x00000000, "(was v7 remap) zero"),
    (TRAMP + 0x34, 0x00000000, "(was v7 remap) zero"),
    (TRAMP + 0x38, 0x00000000, "(was v7 remap) zero"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v8 (autofocus-only trampoline A; Hook B unchanged)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        print("[*] Applied. Aim mode: reticle centered, left-X yaw DEAD (by design).")
        return True


if __name__ == "__main__":
    apply()
