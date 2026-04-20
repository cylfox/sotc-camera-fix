"""v9 (mirror approach): make camera yaw follow aim yaw.

Instead of overriding the matrix builder's $f12 with camera-yaw (which
severs the aim->camera coupling and requires a pad-remap hack), this
hooks the AIM CALLER at 0x013B8314 and mirrors $f20 (the live aim-yaw)
into the camera-yaw register at 0x0106DF00 every frame.

Effect in aim mode:
  - Left-X natively drives aim-yaw (via the game's own input code)
  - Our hook copies aim-yaw -> camera-yaw register each frame
  - Camera renderer follows camera-yaw -> camera follows aim
  - Reticle stays centered (aim direction = camera direction)
  - No pad-byte remap needed; no matrix-builder override needed

Hook B (matrix override at 0x01176AB4) is DISABLED so we test the
mirror approach in isolation. Easy to re-enable later.

Trampoline A (autofocus) stays as-is (v8 shape).

Layout
======
Hook C (2 words) at 0x013B8314..0x013B8318:
    0x013B8314  j 0x001A5268                ; -> trampoline C
    0x013B8318  nop                         ; delay slot (was: jal 0x01176AA0)

Trampoline C (7 words) at 0x001A5268..0x001A5280:
    lui   $at, 0x0107                       ; 0x3C010107
    swc1  $f20, -0x2100($at)                ; 0xE434DF00   0x0106DF00 := $f20
    mov.s $f12, $f20                        ; 0x4600A306   (was @ 0x013B8314)
    jal   0x01176AA0                        ; 0x0C45DAA8   (was @ 0x013B8318)
    mov.s $f13, $f0                         ; 0x46006346   (was @ 0x013B831C - delay slot)
    j     0x013B8320                        ; 0x084EE0C8   return past the original jal
    nop                                     ; 0x00000000

Hook B DISABLE: restore 0x01176AB4 to the original `swc1 $f20, 0xb8($sp)`
(0xE7B400B8) so the matrix builder runs unmodified.

This leaves the PNACH installed state inconsistent (pnach still asserts
the Hook B jump), so we instruct the user to DISABLE the pnach in PCSX2
while testing. Or uncomment the pnach lines.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient


# --- Addresses ---
HOOK_C_SITE = 0x013B8314    # aim-caller's `mov.s $f12, $f20`
HOOK_C_NEXT = 0x013B8318    # aim-caller's `jal 0x01176AA0`
TRAMP_C     = 0x001A5268
HOOK_B_SITE = 0x01176AB4    # original swc1 $f20, 0xb8($sp) -- we restore it


# --- Instruction encodings ---
ORIG_MOVS_F12_F20  = 0x4600A306   # mov.s $f12, $f20
ORIG_JAL_01176AA0  = 0x0C45DAA8   # jal 0x01176AA0
ORIG_MOVS_F13_F0   = 0x46000346   # mov.s $f13, $f0
ORIG_SWC1_F20_SP   = 0xE7B400B8   # swc1 $f20, 0xb8($sp)

TRAMP_C_BODY = [
    (TRAMP_C + 0x00, 0x3C010107,          "lui   $at, 0x0107"),
    (TRAMP_C + 0x04, 0xE434DF00,          "swc1  $f20, -0x2100($at)   ; 0x0106DF00 := $f20"),
    (TRAMP_C + 0x08, ORIG_MOVS_F12_F20,   "mov.s $f12, $f20           ; (was @ 0x013B8314)"),
    (TRAMP_C + 0x0C, ORIG_JAL_01176AA0,   "jal   0x01176AA0           ; (was @ 0x013B8318)"),
    (TRAMP_C + 0x10, ORIG_MOVS_F13_F0,    "mov.s $f13, $f0            ; (was @ 0x013B831C - delay slot)"),
    (TRAMP_C + 0x14, 0x084EE0C8,          "j     0x013B8320           ; return"),
    (TRAMP_C + 0x18, 0x00000000,          "nop"),
]

HOOK_C_PATCHES = [
    (HOOK_C_SITE, 0x0806949A, "j 0x001A5268 -> trampoline C"),
    (HOOK_C_NEXT, 0x00000000, "nop (delay slot; was jal 0x01176AA0)"),
]

HOOK_B_DISABLE = [
    (HOOK_B_SITE, ORIG_SWC1_F20_SP, "restore original swc1 $f20, 0xb8($sp)"),
]


def write_one(pc: PineClient, addr: int, val: int, desc: str) -> bool:
    pc.write_u32(addr, val)
    got = pc.read_u32(addr)
    ok = "OK" if got == val else "FAIL"
    print(f"  0x{addr:08X} <- 0x{val:08X}  [{ok}]  {desc}")
    return got == val


def apply() -> bool:
    with PineClient() as pc:
        print("[*] v9: Mirror aim-yaw -> camera-yaw via hook at 0x013B8314")

        print("[*] Step 1: Disable Hook B (restore original instruction at matrix-builder)")
        for a, v, d in HOOK_B_DISABLE:
            if not write_one(pc, a, v, d):
                return False

        print("[*] Step 2: Install trampoline C body (before the hook jumps to it)")
        for a, v, d in TRAMP_C_BODY:
            if not write_one(pc, a, v, d):
                return False

        print("[*] Step 3: Install hook C at the aim caller site")
        for a, v, d in HOOK_C_PATCHES:
            if not write_one(pc, a, v, d):
                return False

        print("[*] Applied.")
        print("")
        print("Expected behavior in aim mode:")
        print("  - Camera yaw follows aim yaw (left stick X rotates camera)")
        print("  - Reticle stays centered in camera view")
        print("  - No pad-byte remap; vanilla aim input path is used")
        print("")
        print("If the pnach is still enabled in PCSX2, the per-frame patch will")
        print("keep overwriting 0x01176AB4 with the Hook B jump, undoing Step 1.")
        print("Disable the pnach cheat in PCSX2 while testing.")
        return True


def restore() -> bool:
    """Zero out trampoline C and restore the caller-site + Hook B if requested."""
    with PineClient() as pc:
        print("[*] Reverting v9 mirror hook")
        # Restore the caller site (mov.s + jal)
        pc.write_u32(HOOK_C_SITE, ORIG_MOVS_F12_F20)
        pc.write_u32(HOOK_C_NEXT, ORIG_JAL_01176AA0)
        # Zero trampoline C
        for off in range(0, 0x1C, 4):
            pc.write_u32(TRAMP_C + off, 0)
        print("[*] Reverted. (Hook B left as-is; run apply_aim_center or the pnach to re-enable if desired.)")
        return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()
