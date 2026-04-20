"""Live-patch test harness for 0x001ACD44 pad-read.

Reads original word, writes a test patch, waits for user input, restores.

Usage:
    py patch_live.py 2402007F      # patch the word to 0x2402007F
    py patch_live.py 24020081      # patch the word to 0x24020081
"""
import os, sys
import struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

PATCH_ADDR = 0x001ACD44

def main():
    if len(sys.argv) < 2:
        print("usage: py patch_live.py <hex_word>  (e.g. 2402007F)")
        return 1
    new_word = int(sys.argv[1], 16)
    with PineClient() as pc:
        original = pc.read_u32(PATCH_ADDR)
        print(f"[i] original  at 0x{PATCH_ADDR:08X} = 0x{original:08X}")
        print(f"[i] new value at 0x{PATCH_ADDR:08X} = 0x{new_word:08X}")
        print(f"[*] writing patch...")
        pc.write_u32(PATCH_ADDR, new_word)
        verify = pc.read_u32(PATCH_ADDR)
        print(f"[i] verify    at 0x{PATCH_ADDR:08X} = 0x{verify:08X}")
        if verify != new_word:
            print("[!] verification FAILED — not patched. bailing.")
            return 1
        print()
        print("===========================================================")
        print("  Patch active. Test the camera now.")
        print("  - Does auto-focus still fire on stick release?")
        print("  - Does the camera drift without your input?")
        print("  - If so, how fast / in what direction?")
        print("===========================================================")
        print()
        input("[?] press ENTER to RESTORE the original instruction...")
        pc.write_u32(PATCH_ADDR, original)
        verify = pc.read_u32(PATCH_ADDR)
        print(f"[i] restored  at 0x{PATCH_ADDR:08X} = 0x{verify:08X}")
        if verify != original:
            print("[!] restore verification FAILED.")
            return 1
        print("[*] restored OK.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
