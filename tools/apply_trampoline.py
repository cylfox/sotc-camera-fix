"""Apply the conditional-substitute trampoline patch.

Replaces:
  0x001ACD44: lbu v0, 0x107(s2)
  0x001ACD48: sb  v0, 0x57(s0)

With:
  0x001ACD44: j 0x001A4984              (0x08069261)
  0x001ACD48: lbu v0, 0x107(s2)         (0x92420107)   [delay slot: does pad read]

Trampoline at 0x001A4984..0x001A4998:
  0x001A4984: addiu at, zero, 0x80      (0x24010080)
  0x001A4988: bne   v0, at, +2          (0x14410002)
  0x001A498C: nop                       (0x00000000)
  0x001A4990: addiu v0, zero, 0xC0      (0x240200C0)
  0x001A4994: j     0x001ACD4C          (0x0806B353)
  0x001A4998: sb    v0, 0x57(s0)        (0xA2020057)   [delay slot: does store]

Net effect: if real pad byte == 0x80 (exact neutral), substitute 0xC0.
Otherwise pass through. Preserves pitch control for real stick input.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK_ADDR = 0x001ACD44
HOOK_DELAY_ADDR = 0x001ACD48
TRAMPOLINE_ADDR = 0x001A4984

# Conditional substitute with aim-mode bypass.
#
#   aim_mode_flag = mem[0x0106C9F0]     ; 1=free-roam, 0=aim (bow/sword)
#   if aim_mode_flag == 0: skip entirely (pass through real byte)
#   else if v0 in [0x41, 0xBF]: substitute v0 = 0xC0 (kills auto-focus)
#   else: pass through
#   store result, return
PATCHES = [
    # Hook
    (HOOK_ADDR,        0x08069261, "j 0x001A4984"),
    (HOOK_DELAY_ADDR,  0x92420107, "lbu v0, 0x107(s2)           [jump delay slot: pad read]"),
    # Trampoline body
    (0x001A4984,       0x3C010107, "lui at, 0x0107"),
    (0x001A4988,       0x8C21C9FC, "lw at, -0x3604(at)          ; at = mem[0x0106C9FC] (mode flag: 1=free, 0=aim)"),
    (0x001A498C,       0x10200006, "beq at, zero, +6            ; aim mode -> skip substitute entirely"),
    (0x001A4990,       0x00000000, "nop                         [branch delay slot]"),
    (0x001A4994,       0x2441FFBF, "addiu at, v0, -0x41"),
    (0x001A4998,       0x2C21007F, "sltiu at, at, 0x7F          ; at = (v0 in [0x41, 0xBF]) ? 1 : 0"),
    (0x001A499C,       0x10200002, "beq at, zero, +2            ; not in deadzone -> skip substitute"),
    (0x001A49A0,       0x00000000, "nop                         [branch delay slot]"),
    (0x001A49A4,       0x240200C0, "addiu v0, zero, 0xC0        ; substitute: v0 = 0xC0"),
    (0x001A49A8,       0x0806B353, "j 0x001ACD4C"),
    (0x001A49AC,       0xA2020057, "sb v0, 0x57(s0)             [jump delay slot: store]"),
]

ORIGINALS = {
    HOOK_ADDR:       0x92420107,  # lbu v0, 0x107(s2)
    HOOK_DELAY_ADDR: 0xA2020057,  # sb  v0, 0x57(s0)
}


def apply_patch():
    with PineClient() as pc:
        print("[*] Reading pre-patch state for verification...")
        hook_before = pc.read_u32(HOOK_ADDR)
        hook_delay_before = pc.read_u32(HOOK_DELAY_ADDR)
        tramp_before = [pc.read_u32(0x001A4984 + i*4) for i in range(11)]
        print(f"    0x{HOOK_ADDR:08X} = 0x{hook_before:08X}"
              f"  (expect any — may be previous test patch)")
        print(f"    0x{HOOK_DELAY_ADDR:08X} = 0x{hook_delay_before:08X}"
              f"  (expect 0x{ORIGINALS[HOOK_DELAY_ADDR]:08X})")
        print(f"    trampoline region pre-state:")
        for i, w in enumerate(tramp_before):
            a = 0x001A4984 + i * 4
            print(f"      0x{a:08X} = 0x{w:08X}  (expect 0x00000000)")
        if any(w != 0 for w in tramp_before):
            print("[!] WARNING: trampoline region is NOT zero. Aborting so we"
                  " don't clobber something important.")
            return False
        if hook_delay_before != ORIGINALS[HOOK_DELAY_ADDR]:
            print(f"[!] WARNING: 0x{HOOK_DELAY_ADDR:08X} is not the expected"
                  f" original value. Aborting.")
            return False

        print("\n[*] Writing patch...")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"    0x{a:08X}  <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False

        print("\n[*] Patch applied and verified.")
        print("    Near-neutral stick (byte == 0x80) now substitutes to 0xC0.")
        print("    Real non-neutral input passes through unchanged.")
        return True


def restore():
    with PineClient() as pc:
        print("[*] Restoring hook site...")
        for a, v in ORIGINALS.items():
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"    0x{a:08X}  <- 0x{v:08X}  [{ok}]")
        print("[*] Zeroing trampoline...")
        for i in range(11):
            a = 0x001A4984 + i * 4
            pc.write_u32(a, 0)
            got = pc.read_u32(a)
            print(f"    0x{a:08X}  <- 0x00000000  [{'OK' if got == 0 else 'FAIL'}]")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply_patch()
