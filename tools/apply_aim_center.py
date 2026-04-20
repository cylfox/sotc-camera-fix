"""v6: make aim direction = camera direction (FPS-style centered reticle).

Hook at 0x01176AB4 (inside 0x01176AA0's prologue, right before the
jal 0x1B47F0 that consumes $f12). The hook jumps to a small trampoline
that, in aim mode, overwrites $f12 with the live camera yaw at 0x0106DF00.

When the matrix-builder runs it uses camera yaw instead of Wander-aim yaw,
so the aim matrix matches the camera matrix. Aim reticle ends up centered
on screen (same direction as camera view).

Memory layout at 0x001A5248 (trampoline; 8 words used of 34 free):
  0x001A5248  swc1 $f20, 0xb8($sp)   ; restore clobbered instruction
  0x001A524C  lui   t0, 0x0107
  0x001A5250  lw    at, -0x3604(t0)  ; at = mode flag
  0x001A5254  bne   at, zero, +2     ; free-roam -> skip
  0x001A5258  nop
  0x001A525C  lwc1  $f12, -0x2100(t0) ; aim: f12 = mem[0x0106DF00] (camera yaw)
  0x001A5260  j     0x01176ABC       ; return to the jal
  0x001A5264  nop
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176AB4
HOOK_ORIG = 0xE7B400B8   # swc1 $f20, 0xb8($sp)
HOOK_VAL  = 0x08069492   # j 0x001A5248

TRAMP = 0x001A5248

PATCHES = [
    (TRAMP + 0x00, 0xE7B400B8, "swc1 $f20, 0xb8($sp)   ; restore clobbered"),
    (TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107"),
    (TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)     ; at = mode flag"),
    (TRAMP + 0x0C, 0x14200002, "bne at, zero, +2       ; free-roam -> done"),
    (TRAMP + 0x10, 0x00000000, "nop                    [branch delay]"),
    (TRAMP + 0x14, 0xC50CDF00, "lwc1 $f12, -0x2100(t0) ; f12 = mem[0x0106DF00]"),
    (TRAMP + 0x18, 0x0845DAAF, "j 0x01176ABC           ; return to jal"),
    (TRAMP + 0x1C, 0x00000000, "nop                    [jump delay]"),
]


def apply():
    with PineClient() as pc:
        # Verify clean
        for i in range(8):
            v = pc.read_u32(TRAMP + i*4)
            if v != 0:
                print(f"WARN: 0x{TRAMP + i*4:08X} = 0x{v:08X}")
        orig = pc.read_u32(HOOK)
        if orig != HOOK_ORIG:
            print(f"WARN: hook site 0x{HOOK:08X} = 0x{orig:08X}, expected 0x{HOOK_ORIG:08X}")
        print("[*] Writing trampoline...")
        for a, v, _ in PATCHES:
            pc.write_u32(a, v)
        for a, v, desc in PATCHES:
            got = pc.read_u32(a)
            if got != v:
                print(f"FAIL 0x{a:08X}: want {v:08X} got {got:08X}")
                return False
        print("[*] Installing hook...")
        pc.write_u32(HOOK, HOOK_VAL)
        got = pc.read_u32(HOOK)
        print(f"  0x{HOOK:08X} = 0x{got:08X}  [{'OK' if got == HOOK_VAL else 'FAIL'}]")
        print("[*] Applied.")
        return True


def restore():
    with PineClient() as pc:
        pc.write_u32(HOOK, HOOK_ORIG)
        for i in range(8):
            pc.write_u32(TRAMP + i*4, 0)
        print("[*] Restored.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()
