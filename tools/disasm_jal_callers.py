"""For each caller of a given function, dump ~8 instructions before the
jal, highlighting the most recent write to $f12.

Usage:
    py disasm_jal_callers.py 0x01176AA0 < hits.txt
    py disasm_jal_callers.py 0x01176AA0 --addrs 0x011AF960,0x01351960,...

Tries to find the $f12 source (lwc1/mov.s/mtc1) for each caller so we
can tell which one is the aim-yaw path.
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

CONTEXT_BEFORE = 12   # instructions to read before the jal
CONTEXT_AFTER  = 2    # delay slot + 1


def dump_one(pc: PineClient, md, hit_addr: int, func_addr: int) -> None:
    start = hit_addr - 4 * CONTEXT_BEFORE
    end   = hit_addr + 4 * (CONTEXT_AFTER + 1)
    words = []
    for a in range(start, end, 4):
        words.append((a, pc.read_u32(a)))

    print(f"\n=== Caller site 0x{hit_addr:08X} (jal 0x{func_addr:08X}) ===")
    for a, w in words:
        b = w.to_bytes(4, 'little')
        marker = ""
        if a == hit_addr: marker = "  <-- JAL"
        if a == hit_addr + 4: marker = "  <-- delay slot"
        disasm_str = "<cs-fail>"
        note = ""
        if md:
            for insn in md.disasm(b, a):
                disasm_str = f"{insn.mnemonic:<8} {insn.op_str}"
                ops = insn.op_str
                # Any touch of $f12 is highly relevant
                if ops.startswith("$f12"):
                    note = "  ** $f12 **"
                break
        print(f"  0x{a:08X}  {w:08X}  {disasm_str}{marker}{note}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=lambda s: int(s, 0))
    ap.add_argument("--addrs", default=None,
                    help="comma-separated list of caller addresses. If omitted, read from stdin.")
    args = ap.parse_args()

    if args.addrs:
        addrs = [int(s, 0) for s in args.addrs.split(",")]
    else:
        addrs = []
        for line in sys.stdin:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            addrs.append(int(line, 0))

    if not addrs:
        print("no addresses provided")
        return 1

    md = None
    if HAVE_CS:
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
        md.detail = False

    with PineClient() as pc:
        for a in addrs:
            dump_one(pc, md, a, args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
