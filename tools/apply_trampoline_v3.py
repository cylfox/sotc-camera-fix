"""v3 trampoline: auto-focus + aim-direction preserve at a LATER hook point.

Two trampolines cooperating:
  1. Pad-read trampoline (hooked at 0x001ACD44 as before): handles auto-focus
     substitution AND saves the current direction each free-roam frame.
  2. Aim-override trampoline (hooked at 0x01423430 — the shared memcpy return
     that fires LAST per frame in aim mode): in aim mode with counter > 0,
     writes the saved direction into 0x0106C230, defeating the game's
     earlier aim-init writes.

Memory layout in the 39-word free region at 0x001A4984:
  0x001A4984..0x001A49C0  : pad-read tramp (16 instructions)
  0x001A49C4..0x001A49FC  : aim-override tramp (15 instructions)
  0x001A4A00..0x001A4A13  : scratch (saved_quad + counter)
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

PAD_HOOK       = 0x001ACD44
PAD_HOOK_DELAY = 0x001ACD48
AIM_HOOK       = 0x01423430

TRAMP = 0x001A4984
AIM_OV_TRAMP = 0x001A49C4

# Scratch
SAVED = 0x001A4A00   # lq-aligned, 16 bytes
COUNTER = 0x001A4A10

# Original value at aim hook (from earlier read_code.py output)
AIM_HOOK_ORIG = 0xC64001C0  # lwc1 $f0, 0x1C0($s2)

PAD_READ_TRAMP = [
    # Setup + mode check
    (0x001A4984, 0x3C080107, "lui t0, 0x0107          ; t0 = 0x01070000"),
    (0x001A4988, 0x3C09001A, "lui t1, 0x001A          ; t1 = 0x001A0000"),
    (0x001A498C, 0x8D01C9FC, "lw at, -0x3604(t0)      ; at = mem[0x0106C9FC] mode flag"),
    (0x001A4990, 0x1020000A, "beq at, zero, +10       ; aim -> af_skip (no save, no substitute)"),
    (0x001A4994, 0x00000000, "nop                     [branch delay]"),
    # Free-roam: save direction via 128-bit load/store, reset counter
    (0x001A4998, 0x790AC230, "lq t2, -0x3DD0(t0)      ; load 16 bytes from 0x0106C230"),
    (0x001A499C, 0x7D2A4A00, "sq t2, 0x4A00(t1)       ; save to scratch quadword"),
    (0x001A49A0, 0x240D001E, "addiu t5, zero, 30      ; counter reset value"),
    (0x001A49A4, 0xAD2D4A10, "sw t5, 0x4A10(t1)       ; counter = 30"),
    # Auto-focus deadzone check
    (0x001A49A8, 0x2441FFBF, "addiu at, v0, -0x41"),
    (0x001A49AC, 0x2C21007F, "sltiu at, at, 0x7F"),
    (0x001A49B0, 0x10200002, "beq at, zero, +2        ; outside deadzone -> af_skip"),
    (0x001A49B4, 0x00000000, "nop                     [branch delay]"),
    (0x001A49B8, 0x240200C0, "addiu v0, zero, 0xC0    ; substitute"),
    # af_skip: return
    (0x001A49BC, 0x0806B353, "j 0x001ACD4C"),
    (0x001A49C0, 0xA2020057, "sb v0, 0x57(s0)         [jump delay: store]"),
]

AIM_OVERRIDE_TRAMP = [
    # Replay the instruction we clobbered
    (0x001A49C4, 0xC64001C0, "lwc1 f0, 0x1C0(s2)      ; original (replayed)"),
    # Check mode
    (0x001A49C8, 0x3C080107, "lui t0, 0x0107"),
    (0x001A49CC, 0x8D01C9FC, "lw at, -0x3604(t0)      ; mode"),
    (0x001A49D0, 0x14200009, "bne at, zero, +9        ; free-roam -> aov_ret (no override)"),
    (0x001A49D4, 0x00000000, "nop                     [branch delay]"),
    # Check counter
    (0x001A49D8, 0x3C09001A, "lui t1, 0x001A"),
    (0x001A49DC, 0x8D2D4A10, "lw t5, 0x4A10(t1)       ; counter"),
    (0x001A49E0, 0x11A00005, "beq t5, zero, +5        ; counter == 0 -> aov_ret"),
    (0x001A49E4, 0x00000000, "nop                     [branch delay]"),
    # Override: write saved quadword to 0x0106C230
    (0x001A49E8, 0x792A4A00, "lq t2, 0x4A00(t1)       ; load saved"),
    (0x001A49EC, 0x7D0AC230, "sq t2, -0x3DD0(t0)      ; write 0x0106C230 (16 bytes)"),
    (0x001A49F0, 0x25ADFFFF, "addiu t5, t5, -1        ; counter--"),
    (0x001A49F4, 0xAD2D4A10, "sw t5, 0x4A10(t1)       ; store counter"),
    # aov_ret
    (0x001A49F8, 0x08508D0E, "j 0x01423438            ; return to instruction after our hook's delay slot"),
    (0x001A49FC, 0x00000000, "nop                     [jump delay]"),
]

SCRATCH = [
    (0x001A4A00, 0x00000000, "saved_x (init 0)"),
    (0x001A4A04, 0x00000000, "saved_y (init 0)"),
    (0x001A4A08, 0x00000000, "saved_z (init 0)"),
    (0x001A4A0C, 0x00000000, "saved_w (init 0)"),
    (0x001A4A10, 0x00000000, "counter (init 0)"),
]

PAD_HOOK_VAL       = 0x08069261  # j 0x001A4984
PAD_HOOK_DELAY_VAL = 0x92420107  # lbu v0, 0x107(s2)
AIM_HOOK_VAL       = 0x08069271  # j 0x001A49C4  (0x001A49C4/4 = 0x69271)

ORIGINALS = {
    PAD_HOOK:       0x92420107,
    PAD_HOOK_DELAY: 0xA2020057,
    AIM_HOOK:       AIM_HOOK_ORIG,
}


def apply():
    with PineClient() as pc:
        print("[*] Applying v3 (auto-focus + aim-preserve via late-hook)")
        # Step 1: temporarily disable the existing pad-read hook so the
        # game doesn't execute a half-written trampoline
        print("    Step 1: disabling pad-read hook (restoring original lbu)...")
        pc.write_u32(PAD_HOOK, 0x92420107)
        pc.write_u32(PAD_HOOK_DELAY, 0xA2020057)
        # Step 2: write trampoline code + scratch
        print("    Step 2: writing both trampolines + scratch...")
        all_patches = PAD_READ_TRAMP + AIM_OVERRIDE_TRAMP + SCRATCH
        for a, v, _ in all_patches:
            pc.write_u32(a, v)
        # Step 3: verify
        print("    Step 3: verifying...")
        for a, v, desc in all_patches:
            got = pc.read_u32(a)
            if got != v:
                print(f"  FAIL 0x{a:08X}: wrote {v:08X} got {got:08X}  ({desc})")
                return False
        print("    Verified. Step 4: enabling both hooks...")
        # Step 4: enable hooks (body complete, safe to activate)
        pc.write_u32(PAD_HOOK_DELAY, PAD_HOOK_DELAY_VAL)
        pc.write_u32(PAD_HOOK, PAD_HOOK_VAL)
        pc.write_u32(AIM_HOOK, AIM_HOOK_VAL)
        time.sleep(0.1)
        # Verify hooks stuck
        for a, v in [(PAD_HOOK, PAD_HOOK_VAL), (PAD_HOOK_DELAY, PAD_HOOK_DELAY_VAL), (AIM_HOOK, AIM_HOOK_VAL)]:
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  HOOK 0x{a:08X} = 0x{got:08X}  [{ok}]")
        print("[*] Applied.")
        return True


def restore():
    with PineClient() as pc:
        print("[*] Restoring originals + zeroing trampoline...")
        for a, v in ORIGINALS.items():
            pc.write_u32(a, v)
        for i in range(39):
            pc.write_u32(TRAMP + i*4, 0)
        print("[*] Restored.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()
