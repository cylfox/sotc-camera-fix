"""Scan EE code for MIPS instructions that write to FPR f3 (f03).

Classes of writers:
  - lwc1 f3, imm(rs)            : opcode 0x31, ft=3
  - mtc1 rs, f3                 : opcode 0x11, fmt=0x04 (MT), fs=3
  - COP1 single-prec arith fd=3 : opcode 0x11, fmt=0x00 (.S), fd=3
                                  (mov.s, add.s, sub.s, mul.s, div.s, neg.s...)
"""

import sys, struct
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

def decode_f3_write(w: int) -> str | None:
    """Return a human readable label if the 32-bit word writes to f03, else None."""
    opcode = (w >> 26) & 0x3F
    rs = (w >> 21) & 0x1F
    rt = (w >> 16) & 0x1F
    fs = (w >> 11) & 0x1F
    ft = rt  # same bits
    fd = (w >> 6) & 0x1F
    funct = w & 0x3F
    imm = w & 0xFFFF
    imm_s = imm - 0x10000 if imm & 0x8000 else imm

    if opcode == 0x31 and ft == 3:
        return f'lwc1 f3, {imm_s:+d}(r{rs})'
    if opcode == 0x11:
        # check the COP1 sub-format
        fmt = rs  # bits 25:21
        if fmt == 0x04 and fs == 3:  # MT
            return f'mtc1 r{rt}, f3'
        if fmt == 0x00 and fd == 3:  # .S arithmetic, fd=3
            mnem = {0x00:'add.s', 0x01:'sub.s', 0x02:'mul.s', 0x03:'div.s',
                    0x04:'sqrt.s', 0x05:'abs.s', 0x06:'mov.s', 0x07:'neg.s',
                    0x30:'c.f.s', 0x32:'c.eq.s', 0x34:'c.olt.s', 0x3C:'c.lt.s'}.get(funct, f'op_0x{funct:02X}')
            if funct in (0x05, 0x06, 0x07, 0x04):
                return f'{mnem} f3, f{fs}'
            elif funct in range(0x30, 0x40):
                return f'{mnem} f{fs}, f{ft}  (compare — no fd write)'
            else:
                return f'{mnem} f3, f{fs}, f{ft}'
        if fmt == 0x01 and fd == 3:  # .D arithmetic
            return f'(double) op 0x{funct:02X}  f3, f{fs}, f{ft}'
    return None


def main():
    # Scan the camera pipeline code region
    regions = [
        (0x0142B000, 0x10000),  # around 0x0142B398 and outer callers
        (0x01170000, 0x30000),  # around 0x0118E030, 0x0118F3F0, 0x001AExxx
        (0x001A0000, 0x20000),  # around 0x001ACD44, 0x001AEBD0
        (0x0122B000, 0x05000),  # around 0x0122B120, 0x0122D1F8
        (0x0125A000, 0x04000),  # around 0x0125A5C8, 0x0125A708
        (0x01257000, 0x02000),  # around 0x01257CA8
    ]

    hits = []
    with PineClient() as pc:
        for base, size in regions:
            print(f'Scanning 0x{base:08X}..+0x{size:X}...', end=' ', flush=True)
            addr = base
            end = base + size
            region_hits = 0
            while addr < end:
                chunk_size = min(0x8000, end - addr)
                chunk = pc.read_bytes(addr, chunk_size)
                for off in range(0, chunk_size, 4):
                    w = struct.unpack_from('<I', chunk, off)[0]
                    label = decode_f3_write(w)
                    if label and 'compare' not in label:
                        hits.append((addr + off, w, label))
                        region_hits += 1
                addr += chunk_size
            print(f'{region_hits} hits')

    print(f'\nTotal writes to f3: {len(hits)}')
    print(f'{"addr":>10}  {"word":>8}  instruction')
    for a, w, lbl in hits:
        print(f'  0x{a:08X}  {w:08X}  {lbl}')


if __name__ == "__main__":
    main()
