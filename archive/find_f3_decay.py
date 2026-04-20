"""Narrow the f03-writer scan to decay-pattern instructions specifically:
  mul.s f3, f3, fX    (multiplies f03 by something, classic decay/lerp)
  sub.s f3, f3, fX    (subtracts from f03)
  mul.s fY, f3, fX    (uses f03 in mul, may then write elsewhere — skip)
"""
import sys, struct
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

def classify(w: int) -> str | None:
    opcode = (w >> 26) & 0x3F
    if opcode != 0x11: return None
    fmt = (w >> 21) & 0x1F
    ft = (w >> 16) & 0x1F
    fs = (w >> 11) & 0x1F
    fd = (w >> 6) & 0x1F
    funct = w & 0x3F
    if fmt != 0: return None  # only .S
    # Only decay-relevant: fd=3 (write f3) with mul/sub/add
    if fd != 3: return None
    mnem = {0x00:'add.s', 0x01:'sub.s', 0x02:'mul.s', 0x03:'div.s'}.get(funct)
    if not mnem: return None
    return f'{mnem} f3, f{fs}, f{ft}'

def main():
    regions = [
        (0x00100000, 0x400000),  # wide scan for decay candidates
        (0x01100000, 0x400000),
    ]
    hits = []
    with PineClient() as pc:
        for base, size in regions:
            print(f'Scanning 0x{base:08X}..+0x{size:X}...', end=' ', flush=True)
            addr = base
            end = base + size
            region_hits = 0
            while addr < end:
                chunk_size = min(0x10000, end - addr)
                chunk = pc.read_bytes(addr, chunk_size)
                for off in range(0, chunk_size, 4):
                    w = struct.unpack_from('<I', chunk, off)[0]
                    label = classify(w)
                    if label:
                        hits.append((addr + off, w, label))
                        region_hits += 1
                addr += chunk_size
            print(f'{region_hits} hits')
    print(f'\nDecay-pattern writes to f3: {len(hits)}')
    for a, w, lbl in hits:
        print(f'  0x{a:08X}  {w:08X}  {lbl}')

if __name__ == "__main__":
    main()
