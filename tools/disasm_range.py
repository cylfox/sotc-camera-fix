"""Disassemble an arbitrary range, flagging writes to a specified FP register.

Usage: py disasm_range.py 0x013B8058 0x013B8320 --flag-reg f20
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
    HAVE_CS = True
except ImportError:
    HAVE_CS = False


def writes_freg(word: int, fd_target: int) -> bool:
    """Return True if word writes to FP register fd_target.
    Covers: mov.s/mov.d, lwc1, ldc1, mtc1, add.s/sub.s/mul.s/div.s, cvt.*
    """
    op = (word >> 26) & 0x3F

    # lwc1 / ldc1: ft is the dest
    if op in (0x31, 0x35):  # lwc1, ldc1
        ft = (word >> 16) & 0x1F
        return ft == fd_target

    # COP1 (0x11) R-type: fd is bits 10-6 for mov/add/sub/mul/div/cvt
    if op == 0x11:
        fmt = (word >> 21) & 0x1F
        if fmt == 0x04:  # MT -> mtc1 (writes FP fs from GPR rt)
            fs = (word >> 11) & 0x1F
            return fs == fd_target
        if fmt in (0x10, 0x11, 0x14, 0x15):  # S, D, W, L
            fd = (word >> 6) & 0x1F
            return fd == fd_target

    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("start", type=lambda s: int(s, 0))
    ap.add_argument("end", type=lambda s: int(s, 0))
    ap.add_argument("--flag-reg", default="f20", help="FP register to flag writes to, e.g. f20")
    args = ap.parse_args()

    target = int(args.flag_reg.lstrip("fF"))
    print(f"[*] Flagging writes to $f{target} with '***'")

    md = None
    if HAVE_CS:
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
        md.detail = False

    with PineClient() as pc:
        for a in range(args.start, args.end, 4):
            w = pc.read_u32(a)
            b = w.to_bytes(4, 'little')
            disasm_str = "<cs-fail>"
            if md:
                for insn in md.disasm(b, a):
                    disasm_str = f"{insn.mnemonic:<10} {insn.op_str}"
                    break
            flag = "  *** writes $f%d ***" % target if writes_freg(w, target) else ""
            print(f"  0x{a:08X}  {w:08X}  {disasm_str}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
