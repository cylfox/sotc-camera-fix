"""Debug trampoline: logs $s0 (the scratch buffer base) to a watchable memory
location on every pad-byte read. By polling that address during free-roam vs
aim mode, we can see if s0 differs between contexts.

Layout:
  0x001ACD44: j 0x001A4984                    (0x08069261)
  0x001ACD48: lbu v0, 0x107(s2)               (0x92420107)   [jump delay: pad read]

Trampoline at 0x001A4984:
  lui   at, 0x001A                            ; at = 0x001A0000
  sw    s0, 0x4A30(at)                        ; log s0 to 0x001A4A30
  addiu at, v0, -0x41
  sltiu at, at, 0x7F
  beq   at, zero, +2                          ; skip if not in deadzone
  nop
  addiu v0, zero, 0xC0
  j     0x001ACD4C
  sb    v0, 0x57(s0)                          ; delay slot: store

Plus a second logger at 0x001A4A34 logging ra (caller's return addr), so we
can see what context is calling this.
"""
import sys
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

HOOK_ADDR = 0x001ACD44
HOOK_DELAY = 0x001ACD48
TRAMP = 0x001A4984
LOG_S0 = 0x001A4A30   # we'll poll this to see $s0's value
LOG_RA = 0x001A4A34   # we'll poll this to see return address (caller PC)

# Each tuple (addr, value, desc)
PATCHES = [
    (HOOK_ADDR,        0x08069261, "j 0x001A4984"),
    (HOOK_DELAY,       0x92420107, "lbu v0, 0x107(s2)   [delay slot]"),
    # Trampoline body
    (TRAMP + 0x00,     0x3C01001A, "lui at, 0x001A"),
    (TRAMP + 0x04,     0xAC304A30, "sw s0, 0x4A30(at)   ; log s0 -> 0x001A4A30"),
    (TRAMP + 0x08,     0xAC3F4A34, "sw ra, 0x4A34(at)   ; log ra -> 0x001A4A34"),
    (TRAMP + 0x0C,     0x2441FFBF, "addiu at, v0, -0x41"),
    (TRAMP + 0x10,     0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0x14,     0x10200002, "beq at, zero, +2"),
    (TRAMP + 0x18,     0x00000000, "nop [delay slot]"),
    (TRAMP + 0x1C,     0x240200C0, "addiu v0, zero, 0xC0"),
    (TRAMP + 0x20,     0x0806B353, "j 0x001ACD4C"),
    (TRAMP + 0x24,     0xA2020057, "sb v0, 0x57(s0)    [delay slot]"),
]

ORIGINALS = {
    HOOK_ADDR:  0x92420107,
    HOOK_DELAY: 0xA2020057,
}


def apply():
    with PineClient() as pc:
        # Verify trampoline region is zero
        for i in range(12):
            if pc.read_u32(TRAMP + i*4) != 0:
                print(f"[!] trampoline region not zero at 0x{TRAMP + i*4:08X}")
                return False
        # Zero the log slots
        pc.write_u32(LOG_S0, 0)
        pc.write_u32(LOG_RA, 0)
        # Write patches
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            print(f"  0x{a:08X} <- 0x{v:08X}  [{('OK' if got == v else 'FAIL')}]  {desc}")
        print("[*] Debug trampoline applied.")
        return True


def restore():
    with PineClient() as pc:
        for a, v in ORIGINALS.items():
            pc.write_u32(a, v)
        for i in range(12):
            pc.write_u32(TRAMP + i*4, 0)
        pc.write_u32(LOG_S0, 0)
        pc.write_u32(LOG_RA, 0)
        print("[*] Debug trampoline removed.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()
