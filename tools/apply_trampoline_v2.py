"""Extended trampoline: auto-focus disable + aim-direction preserve.

Extends the existing 11-instruction trampoline to add aim-preservation:
  - In free-roam: save current matrix at 0x0106C230 to scratch
  - On transition to aim: counter starts at 30 (reset every free-roam frame)
  - In aim while counter > 0: write saved -> 0x0106C230, decrement counter
  - After counter hits 0: hand off to game's aim logic

Memory layout at 0x001A4984 (fits in the 39-word free region exactly):
  0x001A4984..0x001A4A0F: 35 code words (140 bytes)
  0x001A4A10..0x001A4A1C: 4 scratch words (saved_x, saved_y, saved_z, counter)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK_ADDR = 0x001ACD44
HOOK_DELAY = 0x001ACD48
TRAMP = 0x001A4984

# Scratch memory (at the end of the 39-word free region)
SAVED_X = 0x001A4A10
SAVED_Y = 0x001A4A14
SAVED_Z = 0x001A4A18
COUNTER = 0x001A4A1C

PATCHES = [
    (HOOK_ADDR,      0x08069261, "j 0x001A4984"),
    (HOOK_DELAY,     0x92420107, "lbu v0, 0x107(s2)     [jump delay: pad read]"),
    # --- setup ---
    (TRAMP + 0x00,   0x3C080107, "lui t0, 0x0107        ; t0 = 0x01070000 (camera region base)"),
    (TRAMP + 0x04,   0x3C09001A, "lui t1, 0x001A        ; t1 = 0x001A0000 (scratch region base)"),
    (TRAMP + 0x08,   0x8D01C9FC, "lw at, -0x3604(t0)    ; at = mem[0x0106C9FC] mode flag"),
    (TRAMP + 0x0C,   0x1020000B, "beq at, zero, +11     ; aim mode -> aim_path"),
    (TRAMP + 0x10,   0x00000000, "nop                   [branch delay]"),
    # --- free-roam path: save current matrix, reset counter ---
    (TRAMP + 0x14,   0x8D0AC230, "lw t2, -0x3DD0(t0)    ; t2 = mem[0x0106C230]"),
    (TRAMP + 0x18,   0x8D0BC234, "lw t3, -0x3DCC(t0)    ; t3 = mem[0x0106C234]"),
    (TRAMP + 0x1C,   0x8D0CC238, "lw t4, -0x3DC8(t0)    ; t4 = mem[0x0106C238]"),
    (TRAMP + 0x20,   0xAD2A4A10, "sw t2, 0x4A10(t1)     ; save_x"),
    (TRAMP + 0x24,   0xAD2B4A14, "sw t3, 0x4A14(t1)     ; save_y"),
    (TRAMP + 0x28,   0xAD2C4A18, "sw t4, 0x4A18(t1)     ; save_z"),
    (TRAMP + 0x2C,   0x240D001E, "addiu t5, zero, 30    ; t5 = 30 (override frames)"),
    (TRAMP + 0x30,   0xAD2D4A1C, "sw t5, 0x4A1C(t1)     ; counter = 30"),
    (TRAMP + 0x34,   0x0806927D, "j 0x001A49F4          ; -> af_substitute_check"),
    (TRAMP + 0x38,   0x00000000, "nop                   [jump delay]"),
    # --- aim path: if counter > 0, override 0x0106C230, decrement ---
    (TRAMP + 0x3C,   0x8D2D4A1C, "lw t5, 0x4A1C(t1)     ; t5 = counter"),
    (TRAMP + 0x40,   0x11A00010, "beq t5, zero, +16     ; counter == 0 -> af_skip (no override, no substitute)"),
    (TRAMP + 0x44,   0x00000000, "nop                   [branch delay]"),
    (TRAMP + 0x48,   0x8D2A4A10, "lw t2, 0x4A10(t1)     ; t2 = save_x"),
    (TRAMP + 0x4C,   0x8D2B4A14, "lw t3, 0x4A14(t1)     ; t3 = save_y"),
    (TRAMP + 0x50,   0x8D2C4A18, "lw t4, 0x4A18(t1)     ; t4 = save_z"),
    (TRAMP + 0x54,   0xAD0AC230, "sw t2, -0x3DD0(t0)    ; mem[0x0106C230] = save_x"),
    (TRAMP + 0x58,   0xAD0BC234, "sw t3, -0x3DCC(t0)    ; mem[0x0106C234] = save_y"),
    (TRAMP + 0x5C,   0xAD0CC238, "sw t4, -0x3DC8(t0)    ; mem[0x0106C238] = save_z"),
    (TRAMP + 0x60,   0x25ADFFFF, "addiu t5, t5, -1      ; counter--"),
    (TRAMP + 0x64,   0xAD2D4A1C, "sw t5, 0x4A1C(t1)     ; counter stored"),
    (TRAMP + 0x68,   0x08069282, "j 0x001A4A08          ; -> af_skip"),
    (TRAMP + 0x6C,   0x00000000, "nop                   [jump delay]"),
    # --- af_substitute_check: deadzone check (existing auto-focus logic) ---
    (TRAMP + 0x70,   0x2441FFBF, "addiu at, v0, -0x41"),
    (TRAMP + 0x74,   0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0x78,   0x10200002, "beq at, zero, +2     ; outside deadzone -> af_skip"),
    (TRAMP + 0x7C,   0x00000000, "nop                   [branch delay]"),
    (TRAMP + 0x80,   0x240200C0, "addiu v0, zero, 0xC0  ; substitute"),
    # --- af_skip: return ---
    (TRAMP + 0x84,   0x0806B353, "j 0x001ACD4C"),
    (TRAMP + 0x88,   0xA2020057, "sb v0, 0x57(s0)       [jump delay: store]"),
    # --- scratch (initialized to zero) ---
    (TRAMP + 0x8C,   0x00000000, "saved_x (init 0)"),
    (TRAMP + 0x90,   0x00000000, "saved_y (init 0)"),
    (TRAMP + 0x94,   0x00000000, "saved_z (init 0)"),
    (TRAMP + 0x98,   0x00000000, "counter (init 0)"),
]

ORIGINALS = {
    HOOK_ADDR:  0x92420107,
    HOOK_DELAY: 0xA2020057,
}


def apply():
    with PineClient() as pc:
        print("[*] Applying extended trampoline v2 (auto-focus + aim-preserve)")
        print("    Step 1: writing trampoline body + scratch FIRST (so hook only")
        print("    activates when the target is complete)...")
        hook_patches = [p for p in PATCHES if p[0] in (HOOK_ADDR, HOOK_DELAY)]
        body_patches = [p for p in PATCHES if p[0] not in (HOOK_ADDR, HOOK_DELAY)]
        # Write body first
        for a, v, desc in body_patches:
            pc.write_u32(a, v)
        # Verify body in one pass
        print("    Step 2: verifying body...")
        for a, v, desc in body_patches:
            got = pc.read_u32(a)
            if got != v:
                print(f"  0x{a:08X} FAIL: wrote 0x{v:08X}, read 0x{got:08X}")
                return False
        print("    Body verified. Step 3: installing hook...")
        # Now install hook — trampoline is complete, safe to activate
        for a, v, desc in hook_patches:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            print(f"  HOOK 0x{a:08X} <- 0x{v:08X}  [{('OK' if got == v else 'FAIL')}]")
            if got != v:
                return False
        print("[*] Applied cleanly.")
        return True


def restore():
    with PineClient() as pc:
        print("[*] Restoring original hook + zeroing trampoline region...")
        for a, v in ORIGINALS.items():
            pc.write_u32(a, v)
        # Zero entire 39-word region
        for i in range(39):
            pc.write_u32(TRAMP + i*4, 0)
        print("[*] Restored.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()
