"""v11: v7 + swim bypass + swim autofocus defeat.

Layout (19 instructions at 0x001A4984):
  mode flag (0x0106C9FC):
    != 0 -> free-roam autofocus deadzone check
    == 0 -> check swim flag (0x0106AD90)
              != 0 (swim)  -> DEADZONE check (same defeat as free-roam)
              == 0 (aim)   -> left-X -> right-X scratch remap, then RET

Free-roam and aim behavior is identical to v7. Swim: right-X yaws camera
normally, left-X only drives Wander's swim direction, and right-Y auto-
focus is defeated so the camera holds its pitch when the stick is released
(same behavior as free-roam).

Memory layout at 0x001A4984:
  +0x00 lui   at, 0x0107
  +0x04 lw    at, -0x3604(at)        ; mode flag
  +0x08 bne   at, zero, +9           ; free-roam -> DEADZONE
  +0x0C nop
  +0x10 lui   at, 0x0107
  +0x14 lw    at, -0x5270(at)        ; swim flag 0x0106AD90
  +0x18 bne   at, zero, +5           ; swim -> DEADZONE (autofocus defeat)
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
    (TRAMP + 0x14, 0x8C21AD90, "lw at, -0x5270(at)          ; swim flag 0x0106AD90"),
    (TRAMP + 0x18, 0x14200005, "bne at, zero, DEADZONE(+5)  ; swim -> deadzone (autofocus defeat)"),
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
        print("[*] Applying v11 (v7 + swim bypass + swim autofocus defeat; Hook B unchanged)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        print("[*] Applied. Swim: left=PJ only, right=camera. Aim: unchanged from v7.")
        return True


if __name__ == "__main__":
    apply()
