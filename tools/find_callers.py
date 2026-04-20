"""Find all jal instructions that call a specific target address."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

if len(sys.argv) < 2:
    print("usage: py find_callers.py <target_hex>")
    sys.exit(1)
target = int(sys.argv[1], 16)
jal_encoded = 0x0C000000 | ((target >> 2) & 0x03FFFFFF)
print(f"Target: 0x{target:08X}")
print(f"jal encoding: 0x{jal_encoded:08X}")

# Scan code region
REGIONS = [(0x00100000, 0x400000), (0x00500000, 0x00B00000), (0x01100000, 0x00C00000), (0x01D00000, 0x00200000)]
hits = []
with PineClient() as pc:
    for base, size in REGIONS:
        print(f"Scanning 0x{base:08X}..+0x{size:X}...")
        chunk = 0x40000
        off = 0
        while off < size:
            n = min(chunk, size - off)
            buf = pc.read_bytes(base + off, n)
            for i in range(0, n - 3, 4):
                v = struct.unpack_from('<I', buf, i)[0]
                if v == jal_encoded:
                    hits.append(base + off + i)
            off += n
print(f"\n{len(hits)} caller site(s) found:")
for a in hits:
    print(f"  0x{a:08X}  (returns to 0x{a+8:08X})")
