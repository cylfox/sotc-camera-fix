"""Verify live memory matches the D:\\Documents\\PCSX2 pnach (v7 shipped)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

EXPECTED = [
    (0x0001ACD44, 0x08069261, "Hook A: j 0x001A4984"),
    (0x0001ACD48, 0x92420107, "Hook A: lbu v0, 0x107(s2)"),
    (0x001A4984, 0x3C010107, "TrA: lui at, 0x0107"),
    (0x001A4988, 0x8C21C9FC, "TrA: lw at, -0x3604(at)"),
    (0x001A498C, 0x14200005, "TrA: bne at, zero, +5"),
    (0x001A4990, 0x00000000, "TrA: nop"),
    (0x001A4994, 0x92480108, "TrA: lbu t0, 0x108(s2)"),
    (0x001A4998, 0xA2080056, "TrA: sb t0, 0x56(s0)"),
    (0x001A499C, 0x0806926E, "TrA: j 0x001A49B8"),
    (0x001A49A0, 0x00000000, "TrA: nop"),
    (0x001A49A4, 0x2441FFBF, "TrA: addiu at, v0, -0x41"),
    (0x001A49A8, 0x2C21007F, "TrA: sltiu at, at, 0x7F"),
    (0x001A49AC, 0x10200002, "TrA: beq at, zero, +2"),
    (0x001A49B0, 0x00000000, "TrA: nop"),
    (0x001A49B4, 0x240200C0, "TrA: addiu v0, zero, 0xC0"),
    (0x001A49B8, 0x0806B353, "TrA: j 0x001ACD4C"),
    (0x001A49BC, 0xA2020057, "TrA: sb v0, 0x57(s0)"),
    (0x01176AB4, 0x08069492, "Hook B: j 0x001A5248"),
    (0x001A5248, 0xE7B400B8, "TrB: swc1 $f20, 0xb8($sp)"),
    (0x001A524C, 0x3C080107, "TrB: lui t0, 0x0107"),
    (0x001A5250, 0x8D01C9FC, "TrB: lw at, -0x3604(t0)"),
    (0x001A5254, 0x14200002, "TrB: bne at, zero, +2"),
    (0x001A5258, 0x00000000, "TrB: nop"),
    (0x001A525C, 0xC50CDF00, "TrB: lwc1 $f12, -0x2100(t0)"),
    (0x001A5260, 0x0845DAAF, "TrB: j 0x01176ABC"),
    (0x001A5264, 0x00000000, "TrB: nop"),
]

with PineClient() as pc:
    all_ok = True
    for addr, want, desc in EXPECTED:
        got = pc.read_u32(addr)
        ok = got == want
        marker = "OK" if ok else "MISMATCH"
        if not ok:
            all_ok = False
            print(f"  0x{addr:08X}  want=0x{want:08X} got=0x{got:08X}  [{marker}]  {desc}")
        else:
            print(f"  0x{addr:08X}  0x{got:08X}  [OK]  {desc}")
    print()
    print("[*] ALL MATCH" if all_ok else "[!] MISMATCHES FOUND")
