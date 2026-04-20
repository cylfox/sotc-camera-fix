"""Read and disassemble a range of code."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
    HAVE_CS = True
except ImportError:
    HAVE_CS = False

if len(sys.argv) < 3:
    print("usage: py read_code.py <start_hex> <count>")
    sys.exit(1)
start = int(sys.argv[1], 16)
count = int(sys.argv[2])

with PineClient() as pc:
    words = [pc.read_u32(start + i*4) for i in range(count)]

if HAVE_CS:
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
    for i, w in enumerate(words):
        a = start + i*4
        b = w.to_bytes(4, 'little')
        disasm = "<cs-fail>"
        for insn in md.disasm(b, a):
            disasm = f"{insn.mnemonic} {insn.op_str}"
            break
        print(f"  0x{a:08X}  {w:08X}  {disasm}")
else:
    for i, w in enumerate(words):
        a = start + i*4
        print(f"  0x{a:08X}  {w:08X}")
