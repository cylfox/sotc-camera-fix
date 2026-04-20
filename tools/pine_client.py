"""PINE IPC client for PCSX2 — reads/writes EE memory over localhost TCP.

Wire format (all little-endian):
    request  : u32 length | u8 opcode | u32 addr | payload
    response : u32 length | u8 status | data
    length   : total message size including the 4-byte length field itself
    status   : 0x00 = OK, 0xFF = FAIL

Opcodes taken from PCSX2 pcsx2/PINE.cpp at master.
Windows: PINE listens on 127.0.0.1:<slot>; default slot = 28011.
"""

from __future__ import annotations

import argparse
import socket
import struct
import sys
import time
from dataclasses import dataclass
from typing import Iterable

MSG_READ8 = 0x00
MSG_READ16 = 0x01
MSG_READ32 = 0x02
MSG_READ64 = 0x03
MSG_WRITE8 = 0x04
MSG_WRITE16 = 0x05
MSG_WRITE32 = 0x06
MSG_WRITE64 = 0x07
MSG_VERSION = 0x08
MSG_TITLE = 0x0B
MSG_STATUS = 0x0F

IPC_OK = 0x00
IPC_FAIL = 0xFF

DEFAULT_SLOT = 28011


class PineError(RuntimeError):
    pass


class PineClient:
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_SLOT, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def __enter__(self) -> "PineClient":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = s

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _recv_exact(self, n: int) -> bytes:
        assert self.sock is not None
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise PineError("connection closed by PCSX2")
            buf.extend(chunk)
        return bytes(buf)

    def _exchange(self, opcode: int, body: bytes) -> bytes:
        assert self.sock is not None
        total_len = 4 + 1 + len(body)
        req = struct.pack("<IB", total_len, opcode) + body
        self.sock.sendall(req)

        hdr = self._recv_exact(4)
        (resp_len,) = struct.unpack("<I", hdr)
        if resp_len < 5:
            raise PineError(f"response too short: {resp_len}")
        rest = self._recv_exact(resp_len - 4)
        status = rest[0]
        if status != IPC_OK:
            raise PineError(f"opcode 0x{opcode:02X} failed (status 0x{status:02X})")
        return rest[1:]

    # --- Memory reads ---

    def read_u8(self, addr: int) -> int:
        data = self._exchange(MSG_READ8, struct.pack("<I", addr))
        return data[0]

    def read_u16(self, addr: int) -> int:
        data = self._exchange(MSG_READ16, struct.pack("<I", addr))
        return struct.unpack("<H", data[:2])[0]

    def read_u32(self, addr: int) -> int:
        data = self._exchange(MSG_READ32, struct.pack("<I", addr))
        return struct.unpack("<I", data[:4])[0]

    def read_u64(self, addr: int) -> int:
        data = self._exchange(MSG_READ64, struct.pack("<I", addr))
        return struct.unpack("<Q", data[:8])[0]

    def read_f32(self, addr: int) -> float:
        raw = self.read_u32(addr)
        return struct.unpack("<f", struct.pack("<I", raw))[0]

    def read_bytes(self, addr: int, n: int) -> bytes:
        """Read n bytes starting at addr. n need not be aligned."""
        out = bytearray()
        cur = addr
        remaining = n
        while remaining >= 8:
            out.extend(struct.pack("<Q", self.read_u64(cur)))
            cur += 8
            remaining -= 8
        while remaining >= 4:
            out.extend(struct.pack("<I", self.read_u32(cur)))
            cur += 4
            remaining -= 4
        while remaining >= 2:
            out.extend(struct.pack("<H", self.read_u16(cur)))
            cur += 2
            remaining -= 2
        while remaining >= 1:
            out.append(self.read_u8(cur))
            cur += 1
            remaining -= 1
        return bytes(out)

    # --- Memory writes ---

    def write_u8(self, addr: int, val: int) -> None:
        self._exchange(MSG_WRITE8, struct.pack("<IB", addr, val & 0xFF))

    def write_u16(self, addr: int, val: int) -> None:
        self._exchange(MSG_WRITE16, struct.pack("<IH", addr, val & 0xFFFF))

    def write_u32(self, addr: int, val: int) -> None:
        self._exchange(MSG_WRITE32, struct.pack("<II", addr, val & 0xFFFFFFFF))

    def write_u64(self, addr: int, val: int) -> None:
        self._exchange(MSG_WRITE64, struct.pack("<IQ", addr, val & 0xFFFFFFFFFFFFFFFF))

    # --- Info ---

    def version(self) -> str:
        data = self._exchange(MSG_VERSION, b"")
        return data.rstrip(b"\x00").decode("utf-8", errors="replace")

    def title(self) -> str:
        data = self._exchange(MSG_TITLE, b"")
        return data.rstrip(b"\x00").decode("utf-8", errors="replace")

    def status(self) -> int:
        data = self._exchange(MSG_STATUS, b"")
        return struct.unpack("<I", data[:4])[0]


# --- Snapshot / diff utilities ---

@dataclass
class Diff:
    offset: int
    old: int
    new: int

    def __repr__(self) -> str:
        return f"<Diff +0x{self.offset:04X} 0x{self.old:08X} -> 0x{self.new:08X}>"


def diff_snapshots(a: bytes, b: bytes, word_size: int = 4) -> list[Diff]:
    """Compare two equal-length snapshots word-by-word, return changed offsets."""
    if len(a) != len(b):
        raise ValueError("snapshots must be equal length")
    out: list[Diff] = []
    fmt = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}[word_size]
    for off in range(0, len(a), word_size):
        av = struct.unpack(fmt, a[off:off + word_size])[0]
        bv = struct.unpack(fmt, b[off:off + word_size])[0]
        if av != bv:
            out.append(Diff(off, av, bv))
    return out


def classify_word(raw: int) -> str:
    """Heuristic type label for a 32-bit word."""
    f = struct.unpack("<f", struct.pack("<I", raw))[0]
    if raw == 0:
        return "zero"
    if 0x00100000 <= raw <= 0x02000000:
        return f"ptr(0x{raw:08X})"
    if 0xBF800000 <= raw <= 0x3F800000 or (raw & 0x7F800000) in (0x3F800000, 0x3F000000, 0x40000000, 0x40800000):
        pass
    # reasonable float range? exponent between 2^-10 and 2^10
    exp = (raw >> 23) & 0xFF
    if 0x65 <= exp <= 0x99:  # ~6e-8 .. ~2e8 (wide net)
        return f"f32({f:.4g})"
    if raw < 0x10000:
        return f"u32({raw})"
    return f"u32(0x{raw:08X})"


def poll_words(pc: PineClient, addr: int, n_words: int, duration_s: float, hz: float) -> list[list[int]]:
    """Poll n_words 32-bit values at addr at `hz` for `duration_s`. Returns a list of samples."""
    interval = 1.0 / hz
    end = time.monotonic() + duration_s
    samples: list[list[int]] = []
    while time.monotonic() < end:
        t0 = time.monotonic()
        row = [pc.read_u32(addr + 4 * i) for i in range(n_words)]
        samples.append(row)
        slack = interval - (time.monotonic() - t0)
        if slack > 0:
            time.sleep(slack)
    return samples


def summarize_polls(samples: list[list[int]]) -> list[dict]:
    """Per-word summary: changed? range if float-like? unique count."""
    if not samples:
        return []
    n_words = len(samples[0])
    out = []
    for i in range(n_words):
        col = [row[i] for row in samples]
        unique = set(col)
        floats = [struct.unpack("<f", struct.pack("<I", v))[0] for v in col]
        f_min = min(floats)
        f_max = max(floats)
        out.append({
            "offset": 4 * i,
            "changed": len(unique) > 1,
            "unique": len(unique),
            "first": col[0],
            "last": col[-1],
            "f_min": f_min,
            "f_max": f_max,
        })
    return out


# --- CLI entry points ---

def cmd_selftest(pc: PineClient) -> int:
    print(f"[*] Connected to PINE at {pc.host}:{pc.port}")
    try:
        print(f"    version: {pc.version()!r}")
    except Exception as e:
        print(f"    version query failed: {e}")
    try:
        print(f"    title:   {pc.title()!r}")
    except Exception as e:
        print(f"    title query failed: {e}")

    # Validate known address 1: output camera X (heap, may drift)
    cam_x_addr = 0x01C18710
    try:
        cam_x = pc.read_f32(cam_x_addr)
        print(f"[*] read_f32(0x{cam_x_addr:08X}) = {cam_x:.6f}  (output camera X)")
    except Exception as e:
        print(f"[!] read_f32(0x{cam_x_addr:08X}) failed: {e}")

    # Validate known address 2: code at 0x011EA960 should be `addiu sp, sp, -0x30` = 0x27BDFFD0
    code_addr = 0x011EA960
    expected = 0x27BDFFD0
    try:
        w = pc.read_u32(code_addr)
        ok = "OK" if w == expected else "MISMATCH"
        print(f"[*] read_u32(0x{code_addr:08X}) = 0x{w:08X} (expected 0x{expected:08X})  [{ok}]")
    except Exception as e:
        print(f"[!] read_u32(0x{code_addr:08X}) failed: {e}")

    # Live stream: 30 samples of output camera X at 10 Hz
    print(f"[*] Streaming 30 samples of 0x{cam_x_addr:08X} at 10 Hz — rotate the right stick to see changes")
    for i in range(30):
        try:
            print(f"    [{i:02d}] f32=0x{cam_x_addr:08X} = {pc.read_f32(cam_x_addr):+12.4f}")
        except Exception as e:
            print(f"    [{i:02d}] read failed: {e}")
            return 1
        time.sleep(0.1)
    return 0


def cmd_dump(pc: PineClient, addr: int, length: int) -> int:
    data = pc.read_bytes(addr, length)
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hex_s = " ".join(f"{b:02X}" for b in chunk)
        print(f"0x{addr + off:08X}  {hex_s}")
    return 0


def cmd_poll(pc: PineClient, addr: int, n_words: int, duration: float, hz: float) -> int:
    print(f"[*] Polling {n_words} words at 0x{addr:08X} for {duration:.1f}s @ {hz:.0f} Hz")
    samples = poll_words(pc, addr, n_words, duration, hz)
    summary = summarize_polls(samples)
    print(f"[*] {len(samples)} samples captured")
    print(f"    {'offset':>8}  {'changed':>7}  {'uniq':>5}  {'first':>10}  {'last':>10}  {'f_range':>24}")
    for row in summary:
        f_range = f"{row['f_min']:+.4g} .. {row['f_max']:+.4g}"
        print(f"    +0x{row['offset']:04X}    {str(row['changed']):>7}  {row['unique']:>5}  "
              f"0x{row['first']:08X}  0x{row['last']:08X}  {f_range:>24}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PINE IPC client for PCSX2")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_SLOT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("self-test", help="validate connection and known addresses")

    d = sub.add_parser("dump", help="hex dump N bytes at address")
    d.add_argument("addr", type=lambda s: int(s, 0))
    d.add_argument("length", type=lambda s: int(s, 0))

    p = sub.add_parser("poll", help="poll words at address, summarize change behavior")
    p.add_argument("addr", type=lambda s: int(s, 0))
    p.add_argument("n_words", type=int)
    p.add_argument("--duration", type=float, default=3.0)
    p.add_argument("--hz", type=float, default=30.0)

    args = ap.parse_args(argv)

    try:
        with PineClient(args.host, args.port) as pc:
            if args.cmd == "self-test":
                return cmd_selftest(pc)
            if args.cmd == "dump":
                return cmd_dump(pc, args.addr, args.length)
            if args.cmd == "poll":
                return cmd_poll(pc, args.addr, args.n_words, args.duration, args.hz)
    except (ConnectionRefusedError, socket.timeout) as e:
        print(f"[!] Could not connect to PCSX2 PINE at {args.host}:{args.port}: {e}")
        print("    Enable in PCSX2: Settings > Advanced > Enable PINE (slot 28011)")
        return 2
    except PineError as e:
        print(f"[!] PINE error: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
