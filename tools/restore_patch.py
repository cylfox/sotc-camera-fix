"""Restore the original pad-read instruction."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

PATCH_ADDR = 0x001ACD44
ORIGINAL = 0x92420107  # lbu v0, 0x107(s2)

with PineClient() as pc:
    current = pc.read_u32(PATCH_ADDR)
    print(f"[i] current at 0x{PATCH_ADDR:08X} = 0x{current:08X}")
    pc.write_u32(PATCH_ADDR, ORIGINAL)
    verify = pc.read_u32(PATCH_ADDR)
    print(f"[i] restored to 0x{verify:08X}  (want 0x{ORIGINAL:08X})")
    if verify == ORIGINAL:
        print("[*] OK — original pad-read restored. Normal camera behavior active.")
    else:
        print("[!] restore failed")
