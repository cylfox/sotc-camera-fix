"""Scan EE RAM for MIPS I-type instructions with a specific 16-bit immediate.

Useful for finding references to a specific memory address -- if the address
is `0x0107_XXXX` (encoded as `lui $X, 0x0107; lbu $Y, sign_ext_imm($X)`),
all loads/stores/address-computations of that byte share the same 16-bit
immediate. So searching for that immediate across EE code produces a short
candidate list of references.

Usage
=====
    py find_imm16.py 0xC441                      # find all 0xC441 immediates
    py find_imm16.py 0xC441 --opcode-filter      # only I-type load/store/addiu/ori
    py find_imm16.py 0xC441 --base 0x00100000 --size 0x01F00000

Output
======
For each match, disassembles the instruction (if capstone is available) so
you can see which register, which op, which struct base.
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import threading
import time

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
    HAVE_CS = True
except ImportError:
    HAVE_CS = False


# MIPS opcodes that carry a 16-bit immediate. High 6 bits of the word.
INTERESTING_OPCODES = {
    0x08: "addi",
    0x09: "addiu",
    0x0A: "slti",
    0x0B: "sltiu",
    0x0C: "andi",
    0x0D: "ori",
    0x0E: "xori",
    0x20: "lb",
    0x21: "lh",
    0x22: "lwl",
    0x23: "lw",
    0x24: "lbu",
    0x25: "lhu",
    0x26: "lwr",
    0x27: "lwu",
    0x28: "sb",
    0x29: "sh",
    0x2A: "swl",
    0x2B: "sw",
    0x2E: "swr",
    0x31: "lwc1",
    0x35: "ldc1",
    0x37: "ld",
    0x39: "swc1",
    0x3D: "sdc1",
    0x3F: "sd",
    # Branch immediate (target, not 16-bit data immediate, so skip by default)
}


def worker_scan(host: str, port: int, base: int, length: int,
                imm: int, opcode_filter: bool,
                hits: list, err_box: list, lock: threading.Lock) -> None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(60.0)
        s.connect((host, port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        assert length % 8 == 0
        n_u64 = length // 8
        for i in range(n_u64):
            addr = base + 8 * i
            req = struct.pack("<IBI", 9, 0x03, addr)  # read_u64
            s.sendall(req)
            hdr = b""
            while len(hdr) < 4:
                c = s.recv(4 - len(hdr))
                if not c:
                    raise RuntimeError("closed")
                hdr += c
            (rl,) = struct.unpack("<I", hdr)
            body = b""
            want = rl - 4
            while len(body) < want:
                c = s.recv(want - len(body))
                if not c:
                    raise RuntimeError("closed")
                body += c
            lo = struct.unpack("<I", body[1:5])[0]
            hi = struct.unpack("<I", body[5:9])[0]
            for word_addr, word in ((addr, lo), (addr + 4, hi)):
                if (word & 0xFFFF) != imm:
                    continue
                if opcode_filter:
                    op = (word >> 26) & 0x3F
                    if op not in INTERESTING_OPCODES:
                        continue
                with lock:
                    hits.append((word_addr, word))
        s.close()
    except Exception as e:
        err_box.append(repr(e))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("imm", type=lambda s: int(s, 0),
                    help="16-bit immediate to search for (e.g. 0xC441)")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x00100000)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x01F00000)
    ap.add_argument("--conn", type=int, default=8)
    ap.add_argument("--opcode-filter", action="store_true",
                    help="Only keep hits where opcode is load/store/addiu/ori/etc.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=28011)
    args = ap.parse_args()

    imm16 = args.imm & 0xFFFF
    print(f"[*] Scan for words with low-16 == 0x{imm16:04X}")
    print(f"[*] Range 0x{args.base:08X}..0x{args.base + args.size:08X}  ({args.size // (1024*1024)} MB)")
    print(f"[*] {args.conn} parallel connections, opcode_filter={args.opcode_filter}")

    stride = 8 * args.conn
    size = (args.size // stride) * stride
    per_worker = size // args.conn

    hits: list = []
    errs: list = []
    lock = threading.Lock()
    t0 = time.monotonic()

    threads = [
        threading.Thread(
            target=worker_scan,
            args=(args.host, args.port,
                  args.base + i * per_worker, per_worker,
                  imm16, args.opcode_filter, hits, errs, lock),
            daemon=True,
        )
        for i in range(args.conn)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    dt = time.monotonic() - t0
    if errs:
        print(f"[!] {len(errs)} worker(s) failed: {errs[0]}")
    hits.sort(key=lambda x: x[0])
    print(f"[*] Done in {dt:.1f}s. Found {len(hits)} hits.")

    md = None
    if HAVE_CS:
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
        md.detail = False

    for addr, word in hits:
        op = (word >> 26) & 0x3F
        op_name = INTERESTING_OPCODES.get(op, f"op={op:#04x}")
        disasm = ""
        if md:
            for insn in md.disasm(word.to_bytes(4, "little"), addr):
                disasm = f"  {insn.mnemonic:<10} {insn.op_str}"
                break
        print(f"  0x{addr:08X}  {word:08X}  [{op_name:<6}]{disasm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
