"""Full-EE scan for the 'neutral pitch' constant 0x4091E9F7 (= 4.55981).

This is the value that $f04 returns to during auto-focus snap (per seventh
continuation of SESSION_SUMMARY.md). We've scanned heap regions before with
zero hits -- this script covers the FULL EE address space (code, rodata,
bss, heap) and also sniffs for the MIPS instruction-pair encodings that would
LOAD this constant into an FPR.

Patterns scanned:
  (a) Raw bit pattern 0x4091E9F7 in 4-byte-aligned memory (the constant
      sitting in a .rodata pool, or anywhere else).
  (b) `lui rT, 0x4091` followed by `ori rT, rT, 0xE9F7`
      and then (optionally) `mtc1 rT, fN`.
  (c) `lui rT, 0x4092` followed by `addiu rT, rT, 0xE9F7`
      (addiu sign-extends 0xE9F7 -> -0x1609, so 0x40920000 + -0x1609 = 0x4091E9F7).

Also scans for a couple of neighbor floats we know about:
  - 0x3F71307B = 0.942146  (f04 MAX-down value during hold)
  - 0x3FC7AA7A = 1.55989   (f05 idle value)
  - 0x40C30CB2 = 6.10808... wait, 5.10808 = ?

Let me compute the float for 5.10808 at runtime, but include it as a target.
"""
from __future__ import annotations
import argparse
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient


def f32_to_u32(f: float) -> int:
    return struct.unpack('<I', struct.pack('<f', f))[0]


# Primary target: neutral pitch (what $f04 returns to)
TARGETS_FLOAT = {
    4.55981: "neutral_pitch (f04 idle)",
    -4.55981: "-neutral_pitch",
    0.942146: "f04 max-down",
    1.55989: "f05 idle",
    5.10808: "0x0142B398 exit f04",
}

TARGETS = {f32_to_u32(v): lbl for v, lbl in TARGETS_FLOAT.items()}


# Regions to scan (full EE address range in practical sense)
# PS2 EE RAM = 32 MB at 0x00000000..0x02000000
REGIONS = [
    (0x00100000, 0x00200000, "code 1 (0x00100000..+2MB)"),
    (0x00300000, 0x00200000, "code/rodata 2 (0x00300000..+2MB)"),
    (0x00500000, 0x00300000, "data 1 (0x00500000..+3MB)"),
    (0x00800000, 0x00300000, "data 2 (0x00800000..+3MB)"),
    (0x00B00000, 0x00500000, "data 3 (0x00B00000..+5MB)"),
    (0x01000000, 0x00400000, "heap 1 (0x01000000..+4MB)"),
    (0x01400000, 0x00400000, "heap 2 (0x01400000..+4MB)"),
    (0x01800000, 0x00400000, "heap 3 (0x01800000..+4MB)"),
    (0x01C00000, 0x00300000, "heap 4 (0x01C00000..+3MB)"),
]


def snapshot_worker(host: str, port: int, base: int, start_off: int,
                    n_u64: int, out: bytearray, err_box: list) -> None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(180.0)
        s.connect((host, port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        for i in range(n_u64):
            addr = base + start_off + 8 * i
            req = struct.pack("<IBI", 9, 0x03, addr)
            s.sendall(req)
            hdr = b""
            while len(hdr) < 4:
                c = s.recv(4 - len(hdr))
                if not c:
                    raise RuntimeError("conn closed mid-header")
                hdr += c
            (rl,) = struct.unpack("<I", hdr)
            body = b""
            want = rl - 4
            while len(body) < want:
                c = s.recv(want - len(body))
                if not c:
                    raise RuntimeError("conn closed mid-body")
                body += c
            out[start_off + 8 * i:start_off + 8 * i + 8] = body[1:9]
        s.close()
    except Exception as e:
        err_box.append(repr(e))


def parallel_read(host: str, port: int, base: int, size: int,
                  n_conn: int = 16) -> bytes:
    assert size % 8 == 0
    # Round chunk_bytes so each worker gets whole u64 units.
    chunk_u64_total = size // 8
    per_worker = (chunk_u64_total + n_conn - 1) // n_conn
    actual_conn = (chunk_u64_total + per_worker - 1) // per_worker
    buf = bytearray(size)
    errs: list = []
    threads = []
    for i in range(actual_conn):
        start_u64 = i * per_worker
        end_u64 = min(start_u64 + per_worker, chunk_u64_total)
        n = end_u64 - start_u64
        if n <= 0:
            continue
        t = threading.Thread(
            target=snapshot_worker,
            args=(host, port, base, start_u64 * 8, n, buf, errs),
            daemon=True,
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    if errs:
        raise RuntimeError(f"{len(errs)} worker(s) failed: {errs[0]}")
    return bytes(buf)


def decode_mips_lui(w: int) -> tuple[int, int] | None:
    """Return (rt, imm16) if w is a lui instruction, else None."""
    opcode = (w >> 26) & 0x3F
    rs = (w >> 21) & 0x1F
    if opcode != 0x0F or rs != 0:
        return None
    rt = (w >> 16) & 0x1F
    imm = w & 0xFFFF
    return (rt, imm)


def decode_mips_ori_addiu(w: int) -> tuple[str, int, int, int] | None:
    """Return (mnem, rs, rt, imm) if w is ori (0x0D) or addiu (0x09)."""
    opcode = (w >> 26) & 0x3F
    if opcode not in (0x0D, 0x09):
        return None
    rs = (w >> 21) & 0x1F
    rt = (w >> 16) & 0x1F
    imm = w & 0xFFFF
    mnem = 'ori' if opcode == 0x0D else 'addiu'
    return (mnem, rs, rt, imm)


def decode_mips_mtc1(w: int) -> tuple[int, int] | None:
    """Return (rt, fs) if w is mtc1, else None."""
    opcode = (w >> 26) & 0x3F
    if opcode != 0x11:
        return None
    fmt = (w >> 21) & 0x1F
    if fmt != 0x04:
        return None
    rt = (w >> 16) & 0x1F
    fs = (w >> 11) & 0x1F
    return (rt, fs)


def decode_mips_lwc1(w: int) -> tuple[int, int, int] | None:
    """Return (base_reg, ft, imm16_signed) if w is lwc1, else None."""
    opcode = (w >> 26) & 0x3F
    if opcode != 0x31:  # lwc1
        return None
    base = (w >> 21) & 0x1F
    ft = (w >> 16) & 0x1F
    imm = w & 0xFFFF
    if imm & 0x8000:
        imm -= 0x10000
    return (base, ft, imm)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=28011)
    ap.add_argument("--conn", type=int, default=16)
    ap.add_argument("--no-heap", action="store_true", help="skip heap region")
    args = ap.parse_args()

    regions = list(REGIONS)
    if args.no_heap:
        regions = [r for r in regions if not r[2].startswith("heap")]

    # Collected hits
    const_hits: list[tuple[int, int, str]] = []  # (addr, value, label)
    lui_hits: list[tuple[int, str]] = []          # (addr, annotation)

    for base, size, label in regions:
        t0 = time.monotonic()
        print(f"[*] {label}: 0x{base:08X}..+0x{size:X}  ...", flush=True)
        buf = parallel_read(args.host, args.port, base, size, args.conn)
        dt = time.monotonic() - t0
        mb = size / (1024 * 1024)
        print(f"    read {mb:.1f} MB in {dt:.1f}s ({mb/dt:.2f} MB/s)")

        # Pass 1: scan 4-byte aligned words for target constants.
        region_const_hits = 0
        for off in range(0, size, 4):
            v = struct.unpack_from('<I', buf, off)[0]
            if v in TARGETS:
                const_hits.append((base + off, v, TARGETS[v]))
                region_const_hits += 1
                print(f"    const  0x{base + off:08X}  = 0x{v:08X}  ({TARGETS[v]})")
        if region_const_hits == 0:
            print(f"    (no constant hits in this region)")

        # Pass 2: scan for lui/ori / lui/addiu pairs and optional mtc1.
        for off in range(0, size - 8, 4):
            w1 = struct.unpack_from('<I', buf, off)[0]
            lui = decode_mips_lui(w1)
            if not lui:
                continue
            rt_hi, imm_hi = lui
            w2 = struct.unpack_from('<I', buf, off + 4)[0]
            pair = decode_mips_ori_addiu(w2)
            if not pair:
                continue
            mnem, rs, rt, imm_lo = pair
            if rs != rt_hi or rt != rt_hi:
                continue

            # Compute loaded value
            if mnem == 'ori':
                loaded = ((imm_hi << 16) | imm_lo) & 0xFFFFFFFF
            else:  # addiu (sign-extended)
                sext = imm_lo - 0x10000 if (imm_lo & 0x8000) else imm_lo
                loaded = ((imm_hi << 16) + sext) & 0xFFFFFFFF
            if loaded not in TARGETS:
                continue

            note = f"lui r{rt_hi},0x{imm_hi:04X} + {mnem} r{rt},r{rs},0x{imm_lo:04X}"
            note += f"  -> 0x{loaded:08X} ({TARGETS[loaded]})"
            # Optional third: mtc1 rt -> fN
            if off + 8 < size:
                w3 = struct.unpack_from('<I', buf, off + 8)[0]
                mtc = decode_mips_mtc1(w3)
                if mtc:
                    rt3, fs3 = mtc
                    if rt3 == rt_hi:
                        note += f"  + mtc1 r{rt3},f{fs3}"
            lui_hits.append((base + off, note))
            print(f"    LUIP   0x{base + off:08X}  {note}")

    # --- Report ---
    print(f"\n{'='*70}")
    print(f"Constant-in-memory hits: {len(const_hits)}")
    print(f"{'='*70}")
    # Group by value label
    by_label: dict[str, list[tuple[int, int]]] = {}
    for a, v, lbl in const_hits:
        by_label.setdefault(lbl, []).append((a, v))
    for lbl, locs in sorted(by_label.items()):
        print(f"\n  {lbl}  ({len(locs)} location(s)):")
        for a, v in locs[:30]:
            print(f"    0x{a:08X}  = 0x{v:08X}")
        if len(locs) > 30:
            print(f"    ... and {len(locs) - 30} more")

    print(f"\n{'='*70}")
    print(f"lui/ori-addiu instruction-pair hits: {len(lui_hits)}")
    print(f"{'='*70}")
    for a, note in lui_hits:
        print(f"  0x{a:08X}  {note}")

    # Now for each lui hit, search for lwc1 instructions in the same
    # regions that load from one of the constant-in-memory addresses.
    if const_hits:
        rodata_addrs = [a for a, _v, lbl in const_hits
                        if lbl.startswith("neutral_pitch (f04 idle)")]
        print(f"\n{'='*70}")
        print(f"Searching for lwc1 loads targeting neutral-pitch rodata hits")
        print(f"{'='*70}")
        if not rodata_addrs:
            print("  (no neutral-pitch constant hits -> nothing to look for)")
        else:
            print(f"  rodata candidates: {[hex(a) for a in rodata_addrs]}")
            # Re-read code region and look for lui rB, <high>; lwc1 fN, <low>(rB)
            code_base, code_size, _ = REGIONS[0]
            buf = parallel_read(args.host, args.port, code_base, code_size,
                                args.conn)
            lwc1_hits = []
            for off in range(0, code_size - 8, 4):
                w1 = struct.unpack_from('<I', buf, off)[0]
                lui = decode_mips_lui(w1)
                if not lui:
                    continue
                rt_hi, imm_hi = lui
                # Look at next few instructions for lwc1 using this reg as base
                for d in range(1, 6):  # search next 5 insns
                    if off + 4 * d + 4 > code_size:
                        break
                    wn = struct.unpack_from('<I', buf, off + 4 * d)[0]
                    lwc = decode_mips_lwc1(wn)
                    if not lwc:
                        continue
                    base_reg, ft, imm_s = lwc
                    if base_reg != rt_hi:
                        continue
                    eff = ((imm_hi << 16) + imm_s) & 0xFFFFFFFF
                    if eff in rodata_addrs:
                        lwc1_hits.append((
                            code_base + off,
                            f"lui r{rt_hi},0x{imm_hi:04X}"
                            f" ... (+{d*4}) lwc1 f{ft},{imm_s}(r{base_reg})"
                            f" -> 0x{eff:08X}"))
                        break
            print(f"  lwc1-to-neutral-pitch hits: {len(lwc1_hits)}")
            for a, note in lwc1_hits:
                print(f"    0x{a:08X}  {note}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
