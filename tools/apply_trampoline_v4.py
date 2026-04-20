"""v4: auto-focus + input-aware aim-preserve.

Two trampolines:
  A: pad-read (at 0x001A4984, 19 instructions + 4 scratch words)
     - Saves current 0x0106C230 + pad buffer base $s2 each free-roam frame
     - Handles auto-focus substitution (existing logic)
  B: aim-override (at 0x001A5248, 33 instructions)
     - Hooks at 0x01423430 (shared memcpy return, fires LAST per frame)
     - Reads left-stick bytes from pad buffer (via saved $s2)
     - If left stick NEUTRAL: writes saved direction -> 0x0106C230
     - If left stick PUSHED: saves current direction (user is aiming),
       pass-through so game's aim input takes effect

Effect: camera holds at pre-aim direction while stick is neutral; user
can aim with left stick, and when they release, camera freezes at the
last aimed direction.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

PAD_HOOK       = 0x001ACD44
PAD_HOOK_DELAY = 0x001ACD48
AIM_HOOK       = 0x01423430

PAD_TRAMP = 0x001A4984
AIM_TRAMP = 0x001A5248

# Scratch at end of PAD_TRAMP region
SAVED_X = 0x001A4A10
SAVED_Y = 0x001A4A14
SAVED_Z = 0x001A4A18
S2_STORE = 0x001A4A1C

# Original at AIM_HOOK (lwc1 f0, 0x1C0(s2))
AIM_HOOK_ORIG = 0xC64001C0

# --- Pad-read trampoline ---
PAD_TRAMP_PATCHES = [
    (PAD_TRAMP + 0x00, 0x3C080107, "lui t0, 0x0107"),
    (PAD_TRAMP + 0x04, 0x3C09001A, "lui t1, 0x001A"),
    (PAD_TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)   ; mode flag"),
    (PAD_TRAMP + 0x0C, 0xAD324A1C, "sw s2, 0x4A1C(t1)    ; always save pad-buffer base"),
    (PAD_TRAMP + 0x10, 0x1020000C, "beq at, zero, +12    ; aim -> af_skip"),
    (PAD_TRAMP + 0x14, 0x00000000, "nop"),
    # Free-roam: save current 0x0106C230
    (PAD_TRAMP + 0x18, 0x8D0AC230, "lw t2, -0x3DD0(t0)"),
    (PAD_TRAMP + 0x1C, 0x8D0BC234, "lw t3, -0x3DCC(t0)"),
    (PAD_TRAMP + 0x20, 0x8D0CC238, "lw t4, -0x3DC8(t0)"),
    (PAD_TRAMP + 0x24, 0xAD2A4A10, "sw t2, 0x4A10(t1)    ; saved_x"),
    (PAD_TRAMP + 0x28, 0xAD2B4A14, "sw t3, 0x4A14(t1)    ; saved_y"),
    (PAD_TRAMP + 0x2C, 0xAD2C4A18, "sw t4, 0x4A18(t1)    ; saved_z"),
    # Auto-focus deadzone check
    (PAD_TRAMP + 0x30, 0x2441FFBF, "addiu at, v0, -0x41"),
    (PAD_TRAMP + 0x34, 0x2C21007F, "sltiu at, at, 0x7F"),
    (PAD_TRAMP + 0x38, 0x10200002, "beq at, zero, +2"),
    (PAD_TRAMP + 0x3C, 0x00000000, "nop"),
    (PAD_TRAMP + 0x40, 0x240200C0, "addiu v0, zero, 0xC0"),
    # af_skip (0x001A49C8)
    (PAD_TRAMP + 0x44, 0x0806B353, "j 0x001ACD4C"),
    (PAD_TRAMP + 0x48, 0xA2020057, "sb v0, 0x57(s0)      [jump delay]"),
]

# --- Aim-override trampoline ---
AIM_TRAMP_PATCHES = [
    (AIM_TRAMP + 0x00, 0xC64001C0, "lwc1 f0, 0x1C0(s2)     ; replay original"),
    (AIM_TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107"),
    (AIM_TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)     ; mode"),
    (AIM_TRAMP + 0x0C, 0x1420001B, "bne at, zero, +27      ; free-roam -> aov_ret"),
    (AIM_TRAMP + 0x10, 0x00000000, "nop"),
    (AIM_TRAMP + 0x14, 0x3C09001A, "lui t1, 0x001A"),
    (AIM_TRAMP + 0x18, 0x8D2E4A1C, "lw t6, 0x4A1C(t1)      ; pad buffer base"),
    # Check left stick X
    (AIM_TRAMP + 0x1C, 0x91CF0108, "lbu t7, 0x108(t6)"),
    (AIM_TRAMP + 0x20, 0x39EF0080, "xori t7, t7, 0x80"),
    (AIM_TRAMP + 0x24, 0x2DEF0010, "sltiu t7, t7, 0x10     ; in deadzone?"),
    (AIM_TRAMP + 0x28, 0x11E0000E, "beq t7, zero, +14      ; X pushed -> pass_through"),
    (AIM_TRAMP + 0x2C, 0x00000000, "nop"),
    # Check left stick Y
    (AIM_TRAMP + 0x30, 0x91CF0109, "lbu t7, 0x109(t6)"),
    (AIM_TRAMP + 0x34, 0x39EF0080, "xori t7, t7, 0x80"),
    (AIM_TRAMP + 0x38, 0x2DEF0010, "sltiu t7, t7, 0x10"),
    (AIM_TRAMP + 0x3C, 0x11E00009, "beq t7, zero, +9       ; Y pushed -> pass_through"),
    (AIM_TRAMP + 0x40, 0x00000000, "nop"),
    # Both neutral: override with saved
    (AIM_TRAMP + 0x44, 0x8D2A4A10, "lw t2, 0x4A10(t1)      ; saved_x"),
    (AIM_TRAMP + 0x48, 0x8D2B4A14, "lw t3, 0x4A14(t1)"),
    (AIM_TRAMP + 0x4C, 0x8D2C4A18, "lw t4, 0x4A18(t1)"),
    (AIM_TRAMP + 0x50, 0xAD0AC230, "sw t2, -0x3DD0(t0)"),
    (AIM_TRAMP + 0x54, 0xAD0BC234, "sw t3, -0x3DCC(t0)"),
    (AIM_TRAMP + 0x58, 0xAD0CC238, "sw t4, -0x3DC8(t0)"),
    (AIM_TRAMP + 0x5C, 0x080698B1, "j 0x001A52C4           ; -> aov_ret"),
    (AIM_TRAMP + 0x60, 0x00000000, "nop"),
    # pass_through: update saved to current (user is aiming)
    (AIM_TRAMP + 0x64, 0x8D0AC230, "lw t2, -0x3DD0(t0)     ; current_x"),
    (AIM_TRAMP + 0x68, 0x8D0BC234, "lw t3, -0x3DCC(t0)"),
    (AIM_TRAMP + 0x6C, 0x8D0CC238, "lw t4, -0x3DC8(t0)"),
    (AIM_TRAMP + 0x70, 0xAD2A4A10, "sw t2, 0x4A10(t1)      ; update saved_x"),
    (AIM_TRAMP + 0x74, 0xAD2B4A14, "sw t3, 0x4A14(t1)"),
    (AIM_TRAMP + 0x78, 0xAD2C4A18, "sw t4, 0x4A18(t1)"),
    # aov_ret (0x001A52C4)
    (AIM_TRAMP + 0x7C, 0x08508D0E, "j 0x01423438           ; return"),
    (AIM_TRAMP + 0x80, 0x00000000, "nop"),
]

SCRATCH = [
    (SAVED_X, 0x00000000),
    (SAVED_Y, 0x00000000),
    (SAVED_Z, 0x00000000),
    (S2_STORE, 0x00000000),
]

PAD_HOOK_VAL = 0x08069261        # j 0x001A4984
PAD_DELAY_VAL = 0x92420107       # lbu v0, 0x107(s2)
AIM_HOOK_VAL = 0x08069492        # j 0x001A5248

ORIGINALS = {
    PAD_HOOK:       0x92420107,
    PAD_HOOK_DELAY: 0xA2020057,
    AIM_HOOK:       AIM_HOOK_ORIG,
}


def apply():
    with PineClient() as pc:
        print("[*] Applying v4 (input-aware aim-preserve)")
        print("    Step 1: disabling hooks (restoring originals)...")
        pc.write_u32(PAD_HOOK, 0x92420107)
        pc.write_u32(PAD_HOOK_DELAY, 0xA2020057)
        pc.write_u32(AIM_HOOK, AIM_HOOK_ORIG)
        time.sleep(0.1)
        print("    Step 2: writing trampolines + scratch...")
        # Zero both regions first
        for i in range(39):
            pc.write_u32(PAD_TRAMP + i*4, 0)
        for i in range(34):
            pc.write_u32(AIM_TRAMP + i*4, 0)
        # Write body
        for a, v, _ in PAD_TRAMP_PATCHES + AIM_TRAMP_PATCHES:
            pc.write_u32(a, v)
        for a, v in SCRATCH:
            pc.write_u32(a, v)
        # Verify
        print("    Step 3: verifying...")
        for a, v, desc in PAD_TRAMP_PATCHES + AIM_TRAMP_PATCHES:
            got = pc.read_u32(a)
            if got != v:
                print(f"  FAIL 0x{a:08X}: want {v:08X} got {got:08X}  ({desc})")
                return False
        print("    Step 4: enabling hooks...")
        pc.write_u32(PAD_HOOK_DELAY, PAD_DELAY_VAL)
        pc.write_u32(PAD_HOOK, PAD_HOOK_VAL)
        pc.write_u32(AIM_HOOK, AIM_HOOK_VAL)
        for a, v in [(PAD_HOOK, PAD_HOOK_VAL), (PAD_HOOK_DELAY, PAD_DELAY_VAL), (AIM_HOOK, AIM_HOOK_VAL)]:
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  HOOK 0x{a:08X} = 0x{got:08X}  [{ok}]")
        print("[*] Applied.")
        return True


def restore():
    with PineClient() as pc:
        print("[*] Restoring...")
        for a, v in ORIGINALS.items():
            pc.write_u32(a, v)
        for i in range(39):
            pc.write_u32(PAD_TRAMP + i*4, 0)
        for i in range(34):
            pc.write_u32(AIM_TRAMP + i*4, 0)
        print("[*] Restored.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()
