"""Find any call-like instruction near a given $ra value.

When a BP fires at a callee and we see $ra, we know the caller's
"return-to" address. Normally that's the address immediately after the
caller's jal. But on EE the caller might use jalr, bgezal, etc. -- or
the block might contain VU0 macro ops that confuse static scans.

Strategy: dump a wide window and highlight any word that looks like a
call to the target function OR any indirect call (jalr). Also dump raw
words so the user can pick by eye.

Usage:
    py find_call_near.py 0x013B7FC0 --target 0x01176AA0
"""
from __future__ import annotations

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pine_client import PineClient

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
    HAVE_CS = True
except ImportError:
    HAVE_CS = False


def encode_jal(target: int) -> int:
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def is_jalr(word: int) -> bool:
    # jalr rd, rs = SPECIAL (0x00) | rs<<21 | 0<<16 | rd<<11 | 0<<6 | 0x09
    # func field (bits 5-0) = 0x09, opcode (bits 31-26) = 0x00
    return (word & 0xFC00003F) == 0x00000009


def is_bgezal(word: int) -> bool:
    # REGIMM (0x04) | rs<<21 | 0b10001 <<16 | offset
    # rt field = 0x11 (bgezal) or 0x13 (bgezall) or 0x10 (bltzal) or 0x12 (bltzall)
    if (word >> 26) != 0x01: return False
    rt = (word >> 16) & 0x1F
    return rt in (0x10, 0x11, 0x12, 0x13)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ra", type=lambda s: int(s, 0),
                    help="value of $ra at the breakpoint (return-to address)")
    ap.add_argument("--target", type=lambda s: int(s, 0), default=None,
                    help="target function address (to encode jal)")
    ap.add_argument("--window", type=lambda s: int(s, 0), default=0x100,
                    help="bytes before $ra to dump (default 0x100)")
    args = ap.parse_args()

    needle = encode_jal(args.target) if args.target else None
    start = args.ra - args.window
    end = args.ra + 0x20

    md = None
    if HAVE_CS:
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
        md.detail = False

    with PineClient() as pc:
        print(f"[*] Dumping 0x{start:08X}..0x{end:08X}")
        if needle:
            print(f"[*] jal 0x{args.target:08X} encoded as 0x{needle:08X}")

        for a in range(start, end, 4):
            w = pc.read_u32(a)
            flags = []
            if needle is not None and w == needle:
                flags.append(f"*** jal 0x{args.target:08X} ***")
            if is_jalr(w):
                rs = (w >> 21) & 0x1F
                rd = (w >> 11) & 0x1F
                flags.append(f"*** jalr $r{rd}, $r{rs} ***")
            if is_bgezal(w):
                flags.append("*** bgezal/bltzal ***")
            if a == args.ra:
                flags.append("<-- $ra (return-to)")
            if a == args.ra - 8:
                flags.append("<-- expected jal site")

            b = w.to_bytes(4, 'little')
            disasm_str = ""
            if md:
                for insn in md.disasm(b, a):
                    disasm_str = f"{insn.mnemonic:<10} {insn.op_str}"
                    break
                if not disasm_str:
                    disasm_str = "<cs-fail>"
            flag_str = ("  " + "  ".join(flags)) if flags else ""
            print(f"  0x{a:08X}  {w:08X}  {disasm_str}{flag_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
