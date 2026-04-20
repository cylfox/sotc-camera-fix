"""Find instruction sequences that load the float constant pi/2 (0x3FC90FDB)
into a register, then move it to an FPR."""
import sys, struct
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

def main():
    regions_list = [
        (0x00100000, 0x50000),
        (0x01100000, 0x80000),
        (0x01200000, 0x80000),
        (0x01250000, 0x10000),
        (0x01400000, 0x50000),
    ]
    hits = []
    with PineClient() as pc:
        for region_base, region_size in regions_list:
            print(f'Scanning 0x{region_base:08X}..+0x{region_size:X}...', flush=True)
            addr = region_base
            end = region_base + region_size
            CHUNK = 0x20000
            while addr < end:
                chunk_size = min(CHUNK, end - addr)
                chunk = pc.read_bytes(addr, chunk_size)
                for off in range(0, chunk_size - 4, 4):
                    w = struct.unpack_from('<I', chunk, off)[0]
                    opcode = (w >> 26) & 0x3F
                    rs = (w >> 21) & 0x1F
                    rt = (w >> 16) & 0x1F
                    imm = w & 0xFFFF
                    if opcode == 0x0F and rs == 0 and imm == 0x3FC9:
                        next_w = struct.unpack_from('<I', chunk, off + 4)[0]
                        next_op = (next_w >> 26) & 0x3F
                        next_rs = (next_w >> 21) & 0x1F
                        next_rt = (next_w >> 16) & 0x1F
                        next_imm = next_w & 0xFFFF
                        label = f'lui r{rt}, 0x3FC9'
                        if next_op in (0x0D, 0x09) and next_rs == rt and next_rt == rt and next_imm == 0x0FDB:
                            opname = 'ori' if next_op == 0x0D else 'addiu'
                            label += f' + {opname} r{rt},r{rt},0x0FDB <- PI/2'
                            if off + 8 < chunk_size:
                                w3 = struct.unpack_from('<I', chunk, off + 8)[0]
                                op3 = (w3 >> 26) & 0x3F
                                if op3 == 0x11:
                                    fmt3 = (w3 >> 21) & 0x1F
                                    rt3 = (w3 >> 16) & 0x1F
                                    fs3 = (w3 >> 11) & 0x1F
                                    if fmt3 == 0x04 and rt3 == rt:
                                        label += f' + mtc1 r{rt}, f{fs3}'
                        hits.append((addr + off, label))
                addr += chunk_size
    print(f'\nTotal lui 0x3FC9 hits: {len(hits)}')
    for a, lbl in hits:
        print(f'  0x{a:08X}  {lbl}')

if __name__ == "__main__":
    main()
