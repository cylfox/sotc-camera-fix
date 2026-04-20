"""v7: extended autofocus trampoline with stick remap in aim mode.

In free-roam: same as v1 (deadzone substitute 0xC0 to kill autofocus).
In aim mode: read left-stick-X pad byte (0x108) and write to s0+0x56
  (the scratch slot where camera stored right-stick-X earlier in this
  same pad-decode function). Camera yaw input now driven by left stick.

Combined with the aim-center matrix hook at 0x01176AB4 (separate
trampoline), this gives unified left-stick-only aim: yaw + pitch both
on the left stick, reticle stays centered.

Memory layout at 0x001A4984 (15 instructions, well within 39-word region):
  0x001A4984  lui at, 0x0107                ; 1
  0x001A4988  lw at, -0x3604(at)            ; 2 mode flag
  0x001A498C  bne at, zero, +5              ; 3 free-roam -> deadzone check
  0x001A4990  nop                           ; 4
  # --- aim mode path ---
  0x001A4994  lbu t0, 0x108(s2)             ; 5 left stick X from pad buffer
  0x001A4998  sb t0, 0x56(s0)               ; 6 overwrite right stick X scratch
  0x001A499C  j ret                         ; 7 to 0x001A49B8
  0x001A49A0  nop                           ; 8
  # --- free-roam deadzone check ---
  0x001A49A4  addiu at, v0, -0x41           ; 9
  0x001A49A8  sltiu at, at, 0x7F            ; 10
  0x001A49AC  beq at, zero, +2              ; 11 outside deadzone -> ret
  0x001A49B0  nop                           ; 12
  0x001A49B4  addiu v0, zero, 0xC0          ; 13 substitute
  # --- ret ---
  0x001A49B8  j 0x001ACD4C                  ; 14
  0x001A49BC  sb v0, 0x57(s0)               ; 15 [jump delay slot: store]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984

PATCHES = [
    (TRAMP + 0x00, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x04, 0x8C21C9FC, "lw at, -0x3604(at)          ; mode flag"),
    (TRAMP + 0x08, 0x14200005, "bne at, zero, +5            ; free-roam -> deadzone"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    # Aim path: stick remap
    (TRAMP + 0x10, 0x92480108, "lbu t0, 0x108(s2)           ; left stick X"),
    (TRAMP + 0x14, 0xA2080056, "sb t0, 0x56(s0)             ; overwrite right stick X scratch"),
    (TRAMP + 0x18, 0x0806926E, "j 0x001A49B8                ; -> ret"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    # Free-roam deadzone check
    (TRAMP + 0x20, 0x2441FFBF, "addiu at, v0, -0x41"),
    (TRAMP + 0x24, 0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0x28, 0x10200002, "beq at, zero, +2"),
    (TRAMP + 0x2C, 0x00000000, "nop"),
    (TRAMP + 0x30, 0x240200C0, "addiu v0, zero, 0xC0"),
    # ret
    (TRAMP + 0x34, 0x0806B353, "j 0x001ACD4C"),
    (TRAMP + 0x38, 0xA2020057, "sb v0, 0x57(s0)             [jump delay]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v7 (autofocus + stick remap in aim mode)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        print("[*] Applied.")
        return True


if __name__ == "__main__":
    apply()
