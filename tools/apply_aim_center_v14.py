"""v14: Trampoline B gains a cinematic bail-out gate.

The aim-matrix $f12 override breaks scripted cinematic cameras — during
cutscenes the game calls the same matrix builder and our stale
0x0106DF00 value hijacks the cinematic's intended yaw. Fix: add a
second gate checking 0x0106C880 (=0 during cinematic, =1 during
all gameplay we've sampled). Only apply the $f12 override when
mode_flag==0 AND we're NOT in a cinematic.

Layout at 0x001A5248 (11 instructions, still well within the 34-word
free region):
  +0x00 swc1 $f20, 0xb8($sp)       ; restore clobbered instruction
  +0x04 lui  t0, 0x0107
  +0x08 lw   at, -0x3604(t0)       ; mode flag 0x0106C9FC
  +0x0C bne  at, zero, RET(+5)     ; free-roam -> skip override
  +0x10 nop
  +0x14 lw   at, -0x3780(t0)       ; CINEMATIC gate 0x0106C880 (=0 in cutscene)
  +0x18 beq  at, zero, RET(+2)     ; cinematic -> skip override
  +0x1C nop
  +0x20 lwc1 $f12, -0x2100(t0)     ; f12 = mem[0x0106DF00] (camera yaw)
  +0x24 j    0x01176ABC            ; RET
  +0x28 nop                        ; [jump delay slot]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176AB4
HOOK_ORIG = 0xE7B400B8   # swc1 $f20, 0xb8($sp)
HOOK_VAL  = 0x08069492   # j 0x001A5248

TRAMP = 0x001A5248

PATCHES = [
    (TRAMP + 0x00, 0xE7B400B8, "swc1 $f20, 0xb8($sp)   ; restore clobbered"),
    (TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107"),
    (TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)     ; mode flag 0x0106C9FC"),
    (TRAMP + 0x0C, 0x14200005, "bne at, zero, RET(+5)  ; free-roam -> skip override"),
    (TRAMP + 0x10, 0x00000000, "nop"),
    (TRAMP + 0x14, 0x8D01C880, "lw at, -0x3780(t0)     ; CINEMATIC flag 0x0106C880"),
    (TRAMP + 0x18, 0x10200002, "beq at, zero, RET(+2)  ; cinematic -> skip override"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0xC50CDF00, "lwc1 $f12, -0x2100(t0) ; aim/swim: f12 = camera yaw"),
    (TRAMP + 0x24, 0x0845DAAF, "j 0x01176ABC           ; RET"),
    (TRAMP + 0x28, 0x00000000, "nop                    [jump delay]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v14 aim-center trampoline (with cinematic bail)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        pc.write_u32(HOOK, HOOK_VAL)
        got = pc.read_u32(HOOK)
        hook_ok = "OK" if got == HOOK_VAL else "FAIL"
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  [{hook_ok}]  Hook B: j 0x001A5248")
        print("[*] Applied. Aim override off during cinematics.")
        return True


if __name__ == "__main__":
    apply()
