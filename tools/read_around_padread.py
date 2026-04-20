"""Read and disassemble the instructions around the camera's pad-byte read
at 0x001ACD44, to find space for conditional-patch injection."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
    HAVE_CS = True
except ImportError:
    HAVE_CS = False

START = 0x001ACD30  # 5 instructions before
END   = 0x001ACD70  # ~10 instructions after

def main():
    with PineClient() as pc:
        words = []
        for a in range(START, END, 4):
            w = pc.read_u32(a)
            words.append((a, w))

    # Hex dump
    print(f"{'addr':>10}  {'word':>8}  {'bytes':<11}  disasm")
    print(f"{'-'*10}  {'-'*8}  {'-'*11}  {'-'*30}")
    if HAVE_CS:
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
        md.detail = False
        for a, w in words:
            b = w.to_bytes(4, 'little')
            marker = " <-- TARGET" if a == 0x001ACD44 else ""
            disasm_str = "<cs-fail>"
            for insn in md.disasm(b, a):
                disasm_str = f"{insn.mnemonic} {insn.op_str}"
                break
            print(f"0x{a:08X}  {w:08X}  {b.hex(' ')}  {disasm_str}{marker}")
    else:
        for a, w in words:
            marker = " <-- TARGET" if a == 0x001ACD44 else ""
            b = w.to_bytes(4, 'little')
            print(f"0x{a:08X}  {w:08X}  {b.hex(' ')}{marker}")
        print("[!] capstone not available; install with: pip install capstone")

if __name__ == "__main__":
    main()
