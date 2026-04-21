"""v15: strict-equal aim-flag gate (covers climbing state).

v13 used `beq at, zero, DEADZONE` to skip the remap when the aim flag
(0x0106B484) is 0. That worked for free-roam/swim/on-top-of-colossus
(all = 0), but NOT for climbing — climbing reads `0x0106B484 = 2`,
which passes the `!= zero` test and falls through to the remap, making
left-X yaw the camera again.

v15 adds a subtract-then-branch so we match value == 1 specifically:

  +0x18 addiu at, at, -1         ; at = (aim flag) - 1
  +0x1C bne   at, zero, DEADZONE ; if at != 0 (orig != 1) -> deadzone

This treats every value other than 1 as "not aim", covering climbing
(value 2) and any other previously-unsampled state that happens to read
a non-{0,1} value.

Trampoline A grows from 19 to 20 instructions. All branch/j targets
past +0x18 shift by one word.

Layout (20 instructions at 0x001A4984):
  +0x00 lui   at, 0x0107
  +0x04 lw    at, -0x3604(at)        ; mode flag 0x0106C9FC
  +0x08 bne   at, zero, DEADZONE(+10)
  +0x0C nop
  +0x10 lui   at, 0x0107
  +0x14 lw    at, -0x4B7C(at)        ; aim flag 0x0106B484
  +0x18 addiu at, at, -1              ; [v15] at = aim - 1
  +0x1C bne   at, zero, DEADZONE(+5)  ; [v15] aim != 1 -> deadzone
  +0x20 nop
  +0x24 lbu   t0, 0x108(s2)           ; aim: left-X byte
  +0x28 sb    t0, 0x56(s0)            ; aim: remap
  +0x2C j     0x001A49CC              ; -> RET (new target)
  +0x30 nop
  +0x34 addiu at, v0, -0x41           ; DEADZONE
  +0x38 sltiu at, at, 0x7F
  +0x3C beq   at, zero, RET(+2)
  +0x40 nop
  +0x44 addiu v0, zero, 0xC0
  +0x48 j     0x001ACD4C              ; RET
  +0x4C sb    v0, 0x57(s0)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984

PATCHES = [
    (TRAMP + 0x00, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x04, 0x8C21C9FC, "lw at, -0x3604(at)          ; mode flag"),
    (TRAMP + 0x08, 0x1420000A, "bne at, zero, DEADZONE(+10) ; free-roam -> deadzone"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    (TRAMP + 0x10, 0x3C010107, "lui at, 0x0107              ; reload"),
    (TRAMP + 0x14, 0x8C21B484, "lw at, -0x4B7C(at)          ; AIM flag 0x0106B484"),
    (TRAMP + 0x18, 0x2421FFFF, "addiu at, at, -1            ; at = aim - 1"),
    (TRAMP + 0x1C, 0x14200005, "bne at, zero, DEADZONE(+5)  ; aim != 1 -> deadzone"),
    (TRAMP + 0x20, 0x00000000, "nop"),
    (TRAMP + 0x24, 0x92480108, "lbu t0, 0x108(s2)           ; aim: left-X byte"),
    (TRAMP + 0x28, 0xA2080056, "sb  t0, 0x56(s0)            ; aim: remap"),
    (TRAMP + 0x2C, 0x08069273, "j 0x001A49CC                ; -> RET"),
    (TRAMP + 0x30, 0x00000000, "nop"),
    (TRAMP + 0x34, 0x2441FFBF, "DEADZONE: addiu at, v0, -0x41"),
    (TRAMP + 0x38, 0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0x3C, 0x10200002, "beq at, zero, RET(+2)       ; outside deadzone -> ret"),
    (TRAMP + 0x40, 0x00000000, "nop"),
    (TRAMP + 0x44, 0x240200C0, "addiu v0, zero, 0xC0        ; substitute"),
    (TRAMP + 0x48, 0x0806B353, "RET: j 0x001ACD4C"),
    (TRAMP + 0x4C, 0xA2020057, "sb v0, 0x57(s0)             [delay slot]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v15 (strict aim == 1 gate; Trampoline B unchanged)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        print("[*] Applied. Remap fires only when aim flag == 1.")
        return True


if __name__ == "__main__":
    apply()
