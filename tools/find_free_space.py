"""Find runs of consecutive 0x00000000 words in the code region (free padding
between functions) that could host a trampoline hook."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

MIN_RUN = 6   # need at least 6 consecutive zero words (24 bytes) for our trampoline

def main():
    # Code region of PAL SotC EE: roughly 0x00100000..0x00400000
    base = 0x00100000
    size = 0x00400000
    chunk_sz = 0x10000
    runs = []  # (start_addr, length_words)
    with PineClient() as pc:
        addr = base
        end = base + size
        while addr < end:
            cs = min(chunk_sz, end - addr)
            buf = pc.read_bytes(addr, cs)
            # Find runs of zero words
            i = 0
            while i < cs - 3:
                if struct.unpack_from('<I', buf, i)[0] == 0:
                    j = i + 4
                    while j < cs - 3 and struct.unpack_from('<I', buf, j)[0] == 0:
                        j += 4
                    run_len_words = (j - i) // 4
                    if run_len_words >= MIN_RUN:
                        runs.append((addr + i, run_len_words))
                    i = j
                else:
                    i += 4
            addr += cs
            print(f"  scanned 0x{addr:08X}", end='\r', flush=True)
    print(f"\nFound {len(runs)} runs of >= {MIN_RUN} zero words:")
    for a, n in runs[:50]:
        print(f"  0x{a:08X}  length {n} words ({n*4} bytes)")
    if len(runs) > 50:
        print(f"  ... and {len(runs) - 50} more")

    # Highlight ones close to our target (0x001ACD44) for minimal branch-distance
    near = [(a, n) for a, n in runs if abs(a - 0x001ACD44) < 0x20000]
    print(f"\nRuns within 128 KB of 0x001ACD44:")
    for a, n in near[:20]:
        print(f"  0x{a:08X}  {n} words  (distance {a - 0x001ACD44:+})")

if __name__ == "__main__":
    main()
