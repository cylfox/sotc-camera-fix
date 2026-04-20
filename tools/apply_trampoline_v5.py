"""v5: matrix-source override via hook inside 0x01176AA0.

Hook point: 0x01176AC8 (instruction between matrix-build and matrix-use)
   Original: addiu $a1, $sp, 0x40   (a1 = sp+0x40, the matrix source)
   Replaced with: j our_tramp

Trampoline at 0x001A5248 does:
  - Restore the clobbered instruction (a1 = sp+0x40)
  - Read mode flag at 0x0106C9FC
  - If free-roam (1): save matrix from sp+0x40 to scratch (48 bytes / 3 quadwords)
  - If aim mode (0): overwrite matrix at sp+0x40 with saved
  - j back to 0x01176AD0 (the jal that uses the matrix)

Scratch (at end of region, 16-byte aligned):
  0x001A52A0..0x001A52CF : saved matrix (48 bytes)
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176AC8
HOOK_ORIG = 0x27A50040  # addiu $a1, $sp, 0x40
HOOK_VAL  = 0x08069492  # j 0x001A5248

TRAMP = 0x001A5248

PATCHES = [
    # Instruction 1: restore clobbered
    (TRAMP + 0x00, 0x27A50040, "addiu a1, sp, 0x40       ; restore clobbered"),
    # Setup: load base registers
    (TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107           ; camera region"),
    (TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)       ; at = mode flag"),
    (TRAMP + 0x0C, 0x3C09001A, "lui t1, 0x001A           ; scratch region"),
    # Branch on mode
    (TRAMP + 0x10, 0x14200009, "bne at, zero, save_path  ; free-roam -> save"),
    (TRAMP + 0x14, 0x00000000, "nop                      [branch delay]"),
    # Aim path: OVERRIDE matrix at sp+0x40 with saved
    (TRAMP + 0x18, 0x792A52A0, "lq t2, 0x52A0(t1)        ; saved row 0+1 lo"),
    (TRAMP + 0x1C, 0x7FAA0040, "sq t2, 0x40(sp)          ; -> matrix row 0"),
    (TRAMP + 0x20, 0x792A52B0, "lq t2, 0x52B0(t1)        ; saved row 1"),
    (TRAMP + 0x24, 0x7FAA0050, "sq t2, 0x50(sp)          ; -> matrix row 1"),
    (TRAMP + 0x28, 0x792A52C0, "lq t2, 0x52C0(t1)        ; saved row 2"),
    (TRAMP + 0x2C, 0x7FAA0060, "sq t2, 0x60(sp)          ; -> matrix row 2"),
    (TRAMP + 0x30, 0x08069A66, "j ret                    ; return"),
    (TRAMP + 0x34, 0x00000000, "nop                      [jump delay]"),
    # save_path: store matrix from sp+0x40 into scratch
    (TRAMP + 0x38, 0x7BAA0040, "lq t2, 0x40(sp)          ; matrix row 0"),
    (TRAMP + 0x3C, 0x7D2A52A0, "sq t2, 0x52A0(t1)        ; -> saved[0]"),
    (TRAMP + 0x40, 0x7BAA0050, "lq t2, 0x50(sp)          ; matrix row 1"),
    (TRAMP + 0x44, 0x7D2A52B0, "sq t2, 0x52B0(t1)        ; -> saved[1]"),
    (TRAMP + 0x48, 0x7BAA0060, "lq t2, 0x60(sp)          ; matrix row 2"),
    (TRAMP + 0x4C, 0x7D2A52C0, "sq t2, 0x52C0(t1)        ; -> saved[2]"),
    # ret: return to 0x01176AD0 (the jal)
    (TRAMP + 0x50, 0x0845DAB4, "j 0x01176AD0             ; return to jal"),
    (TRAMP + 0x54, 0x00000000, "nop                      [jump delay]"),
    # Scratch (16-byte aligned, 48 bytes)
    (TRAMP + 0x58, 0x00000000, "saved[0] (init 0)"),
    (TRAMP + 0x5C, 0x00000000, "saved[1] (init 0)"),
    (TRAMP + 0x60, 0x00000000, "saved[2] (init 0)"),
    (TRAMP + 0x64, 0x00000000, "saved[3] (init 0)"),
    (TRAMP + 0x68, 0x00000000, "saved[4] (init 0)"),
    (TRAMP + 0x6C, 0x00000000, "saved[5] (init 0)"),
    (TRAMP + 0x70, 0x00000000, "saved[6] (init 0)"),
    (TRAMP + 0x74, 0x00000000, "saved[7] (init 0)"),
    (TRAMP + 0x78, 0x00000000, "saved[8] (init 0)"),
    (TRAMP + 0x7C, 0x00000000, "saved[9] (init 0)"),
    (TRAMP + 0x80, 0x00000000, "saved[10] (init 0)"),
    (TRAMP + 0x84, 0x00000000, "saved[11] (init 0)"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v5 (matrix-source override)")
        # Verify region is clean
        for i in range(34):
            v = pc.read_u32(TRAMP + i*4)
            if v != 0:
                print(f"  WARN trampoline region 0x{TRAMP + i*4:08X} = 0x{v:08X} (not zero)")
        print("    Step 1: writing trampoline body...")
        for a, v, _ in PATCHES:
            pc.write_u32(a, v)
        print("    Step 2: verifying...")
        for a, v, desc in PATCHES:
            got = pc.read_u32(a)
            if got != v:
                print(f"  FAIL 0x{a:08X}: want {v:08X} got {got:08X}  ({desc})")
                return False
        print("    Step 3: installing hook...")
        pc.write_u32(HOOK, HOOK_VAL)
        got = pc.read_u32(HOOK)
        print(f"  HOOK 0x{HOOK:08X} = 0x{got:08X}  [{'OK' if got == HOOK_VAL else 'FAIL'}]")
        print("[*] v5 applied.")
        return True


def restore():
    with PineClient() as pc:
        print("[*] Restoring v5...")
        pc.write_u32(HOOK, HOOK_ORIG)
        for i in range(34):
            pc.write_u32(TRAMP + i*4, 0)
        print("[*] Restored.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()
