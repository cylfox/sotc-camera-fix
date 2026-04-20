"""Disassemble the matrix-builder region around our Hook B site.

Hook B replaces the instruction at 0x01176AB4 (was `swc1 $f20, 0xb8($sp)`)
with a jump to our trampoline at 0x001A5248, which overrides $f12 with
mem[0x0106DF00] before continuing to the `jal 0x1B47F0` at 0x01176ABC.

We want to know: in vanilla execution, what value does $f12 hold at the
jal? That's the aim-yaw source. The load / move that set $f12 must be
*before* 0x01176AB4 (so it's unmodified by our hook), and the `jal
0x1B47F0` consumes $f12 right after.

Strategy: dump a comfortable window before and after the hook, annotate
any instruction that writes to $f12 or that looks like an angle source
(lwc1, mov.s, mfc1, cvt.s.w, etc.).

Run this while PCSX2 is up with the game running (doesn't matter what
mode -- we're reading static code bytes).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
    HAVE_CS = True
except ImportError:
    HAVE_CS = False

# Matrix builder function starts at 0x01176AA0 per research notes.
# Back up a bit further in case $f12 is set by the caller / earlier.
START = 0x01176A80   # 13 instructions before the hook
END   = 0x01176AE0   # ~11 instructions after

HOOK_SITE = 0x01176AB4       # our trampoline B hook (was swc1 $f20, 0xb8($sp))
JAL_SITE  = 0x01176ABC       # jal 0x1B47F0 -- consumes $f12 as aim yaw
FUNC_HEAD = 0x01176AA0       # matrix-builder prologue


def annotate(insn):
    """Return a string flag if this instruction touches $f12 or looks yaw-y."""
    m, op = insn.mnemonic, insn.op_str
    flags = []
    # Anything that writes to $f12 (left-hand reg in MIPS FP dest-first syntax)
    if op.startswith("$f12") or op.startswith("f12"):
        flags.append("** writes/reads $f12 **")
    # Float loads are the likely vehicle for an angle coming from memory
    if m in ("lwc1", "ldc1"):
        flags.append("(float load)")
    # mov.s / cvt pass angles around between FP regs
    if m in ("mov.s", "cvt.s.w", "cvt.s.d", "mtc1"):
        flags.append("(fp move/convert)")
    return " ".join(flags)


def main():
    with PineClient() as pc:
        words = []
        for a in range(START, END, 4):
            w = pc.read_u32(a)
            words.append((a, w))

    print(f"{'addr':>10}  {'word':>8}  disasm")
    print(f"{'-'*10}  {'-'*8}  {'-'*60}")
    if not HAVE_CS:
        for a, w in words:
            print(f"0x{a:08X}  {w:08X}")
        print("[!] capstone not available; install with: pip install capstone")
        return

    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    for a, w in words:
        b = w.to_bytes(4, 'little')
        marks = []
        if a == FUNC_HEAD: marks.append("<-- FUNC HEAD (0x01176AA0)")
        if a == HOOK_SITE: marks.append("<-- HOOK B (was swc1 $f20, 0xb8($sp))")
        if a == JAL_SITE:  marks.append("<-- jal 0x1B47F0 (consumes $f12)")
        marker = "  " + " ".join(marks) if marks else ""

        disasm_str = "<cs-fail>"
        note = ""
        for insn in md.disasm(b, a):
            disasm_str = f"{insn.mnemonic:<8} {insn.op_str}"
            note = annotate(insn)
            break
        if note:
            marker = (marker + "  " + note) if marker else ("  " + note)
        print(f"0x{a:08X}  {w:08X}  {disasm_str}{marker}")


if __name__ == "__main__":
    main()
