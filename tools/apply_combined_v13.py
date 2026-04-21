"""v13: v12 with a non-latching aim-specific flag.

v12 used 0x0106B528 as a "not-aim" flag, but it reads 0 in "on top of
colossus" too (so the remap wrongly fired there). v13 uses 0x0106B484,
which was verified = 1 only in aim mode and = 0 in free-roam, swim, and
on-colossus. Flips cleanly on aim entry/exit (unlike 0x0106AF14, which
latched high after first aim).

Behavior inside the mode_flag == 0 branch:
  aim flag != 0 (aim)     -> left-X -> right-X scratch remap
  aim flag == 0 (anything else) -> DEADZONE (autofocus defeat, no remap)

Layout (19 instructions at 0x001A4984, same shape as v11/v12):
  +0x00 lui   at, 0x0107
  +0x04 lw    at, -0x3604(at)        ; mode flag 0x0106C9FC
  +0x08 bne   at, zero, +9           ; free-roam -> DEADZONE
  +0x0C nop
  +0x10 lui   at, 0x0107
  +0x14 lw    at, -0x4B7C(at)        ; AIM flag 0x0106B484        [v13]
  +0x18 beq   at, zero, +5           ; NOT aim -> DEADZONE        [v13: was bne]
  +0x1C nop
  +0x20 lbu   t0, 0x108(s2)          ; aim: left-X byte
  +0x24 sb    t0, 0x56(s0)           ; aim: remap to right-X scratch
  +0x28 j     0x001A49C8             ; -> RET
  +0x2C nop
  +0x30 addiu at, v0, -0x41          ; DEADZONE
  +0x34 sltiu at, at, 0x7F
  +0x38 beq   at, zero, +2           ; outside -> RET
  +0x3C nop
  +0x40 addiu v0, zero, 0xC0
  +0x44 j     0x001ACD4C             ; RET
  +0x48 sb    v0, 0x57(s0)           ; [jump delay slot]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984

PATCHES = [
    (TRAMP + 0x00, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x04, 0x8C21C9FC, "lw at, -0x3604(at)          ; mode flag 0x0106C9FC"),
    (TRAMP + 0x08, 0x14200009, "bne at, zero, DEADZONE(+9)  ; free-roam -> deadzone"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    (TRAMP + 0x10, 0x3C010107, "lui at, 0x0107              ; reload"),
    (TRAMP + 0x14, 0x8C21B484, "lw at, -0x4B7C(at)          ; AIM flag 0x0106B484"),
    (TRAMP + 0x18, 0x10200005, "beq at, zero, DEADZONE(+5)  ; not aim -> deadzone"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0x92480108, "lbu t0, 0x108(s2)           ; aim: left-X byte"),
    (TRAMP + 0x24, 0xA2080056, "sb  t0, 0x56(s0)            ; aim: remap to right-X scratch"),
    (TRAMP + 0x28, 0x08069272, "j 0x001A49C8                ; -> RET"),
    (TRAMP + 0x2C, 0x00000000, "nop"),
    (TRAMP + 0x30, 0x2441FFBF, "DEADZONE: addiu at, v0, -0x41"),
    (TRAMP + 0x34, 0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0x38, 0x10200002, "beq at, zero, RET(+2)       ; outside deadzone -> ret"),
    (TRAMP + 0x3C, 0x00000000, "nop"),
    (TRAMP + 0x40, 0x240200C0, "addiu v0, zero, 0xC0        ; substitute"),
    (TRAMP + 0x44, 0x0806B353, "RET: j 0x001ACD4C"),
    (TRAMP + 0x48, 0xA2020057, "sb v0, 0x57(s0)             [delay slot]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v13 (aim-only remap via 0x0106B484; Hook B unchanged)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        print("[*] Applied. Aim-only remap. Everything else: deadzone substitute.")
        return True


if __name__ == "__main__":
    apply()
