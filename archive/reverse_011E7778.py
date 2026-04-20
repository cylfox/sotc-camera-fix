"""Read code bytes at 0x011E7778 via PINE, disassemble as MIPS64, and
resolve the camera controller root pointer.

Typical small-helper patterns we expect:

    lui   vX, %hi(SYM)            ; returns &SYM
    addiu vX, vX, %lo(SYM)
    jr    ra

or:

    lui   vX, %hi(SYM)            ; returns *SYM (SYM holds the pointer)
    lw    vX, %lo(SYM)(vX)
    jr    ra

Both give us the absolute SYM address = (hi << 16) + sign_extend16(lo).
"""

from __future__ import annotations

import argparse
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN

from pine_client import PineClient, PineError, DEFAULT_SLOT

DEFAULT_FUNC_ADDR = 0x011E7778
DEFAULT_READ_LEN = 0x200  # 512 bytes — small helper expected


def sign_extend_16(x: int) -> int:
    return x - 0x10000 if x & 0x8000 else x


def disasm(md: Cs, code: bytes, base: int) -> list:
    """Return list of (addr, mnemonic, op_str, bytes)."""
    out = []
    for ins in md.disasm(code, base):
        out.append((ins.address, ins.mnemonic, ins.op_str, ins.bytes))
    return out


def find_function_end(instrs: list) -> int | None:
    """Return index of the `jr ra` delay-slot instruction (i.e., end+1 of func)."""
    for i, (_, mnem, ops, _) in enumerate(instrs):
        if mnem == "jr" and "ra" in ops:
            return i + 1  # include the delay slot
    return None


def resolve_hi_lo(instrs: list) -> list[dict]:
    """Find (lui, ... rX with 16-bit imm using same rX) pairs and compute resolved addresses.

    Returns a list of dicts: {hi_addr, lo_addr, reg, hi, lo, resolved, kind}
    where kind ∈ {"addr", "load"}.
    """
    results: list[dict] = []
    # Track last lui per register
    last_lui: dict[str, tuple[int, int]] = {}  # reg -> (addr, imm_hi)
    for addr, mnem, ops, _ in instrs:
        parts = [p.strip() for p in ops.split(",")]
        if mnem == "lui" and len(parts) == 2:
            try:
                imm = int(parts[1], 0)
            except ValueError:
                continue
            last_lui[parts[0]] = (addr, imm)
            continue

        # addiu rX, rY, imm  — treat addiu rX, rY, lo(SYM) where rY has a pending lui
        if mnem == "addiu" and len(parts) == 3:
            dst, src, imm_s = parts
            if src in last_lui:
                try:
                    imm_lo = int(imm_s, 0)
                except ValueError:
                    continue
                hi_addr, hi = last_lui[src]
                resolved = (hi << 16) + sign_extend_16(imm_lo & 0xFFFF)
                results.append({
                    "hi_addr": hi_addr, "lo_addr": addr, "reg": dst,
                    "hi": hi, "lo": imm_lo, "resolved": resolved & 0xFFFFFFFF,
                    "kind": "addr",  # address of SYM
                })
                # rY may still be usable for additional refs; keep last_lui
            continue

        # lw rX, offset(rY)
        if mnem in ("lw", "ld", "lh", "lb", "lbu", "lhu", "lwu") and len(parts) == 2:
            off_reg = parts[1]
            if "(" in off_reg and off_reg.endswith(")"):
                off_str, reg = off_reg[:-1].split("(", 1)
                if reg in last_lui:
                    try:
                        off = int(off_str, 0)
                    except ValueError:
                        continue
                    hi_addr, hi = last_lui[reg]
                    resolved = (hi << 16) + sign_extend_16(off & 0xFFFF)
                    results.append({
                        "hi_addr": hi_addr, "lo_addr": addr, "reg": parts[0],
                        "hi": hi, "lo": off, "resolved": resolved & 0xFFFFFFFF,
                        "kind": "load",  # value loaded from SYM
                    })
            continue

    return results


def print_disasm(instrs: list, end_idx: int | None) -> None:
    for i, (addr, mnem, ops, raw) in enumerate(instrs):
        marker = ""
        if end_idx is not None and i == end_idx - 1:
            marker = "   ; <-- delay slot / end of function"
        elif end_idx is not None and i >= end_idx:
            marker = "   ; (past function end)"
        raw_hex = " ".join(f"{b:02X}" for b in raw)
        print(f"  0x{addr:08X}  {raw_hex:<12}  {mnem:<8} {ops}{marker}")


def run(host: str, port: int, func_addr: int, length: int) -> int:
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
    md.detail = False

    with PineClient(host, port) as pc:
        print(f"[*] Reading {length} bytes at 0x{func_addr:08X} via PINE")
        code = pc.read_bytes(func_addr, length)

    instrs = disasm(md, code, func_addr)
    if not instrs:
        print("[!] No instructions decoded — code may be junk or address wrong.")
        return 1

    end_idx = find_function_end(instrs)
    end_note = f"{end_idx} instructions (incl. delay slot)" if end_idx else "not found"
    print(f"[*] Function end: {end_note}")

    print(f"[*] Disassembly of 0x{func_addr:08X}:")
    print_disasm(instrs[:end_idx + 4] if end_idx else instrs, end_idx)

    # Prologue sanity check
    if instrs and instrs[0][1] == "addiu" and "sp" in instrs[0][2]:
        print(f"[*] Prologue looks normal: {instrs[0][1]} {instrs[0][2]}")
    elif end_idx is not None and end_idx <= 6:
        print("[*] No stack frame — leaf helper (expected for a trivial accessor).")
    else:
        print("[!] Unusual prologue — double-check the function address.")

    # Resolve hi/lo pairs (limited to body of function if we found its end)
    body = instrs[:end_idx] if end_idx else instrs
    refs = resolve_hi_lo(body)
    if refs:
        print("[*] Resolved hi/lo references:")
        for r in refs:
            kind = "&SYM" if r["kind"] == "addr" else "*SYM"
            print(f"    hi@0x{r['hi_addr']:08X} + lo@0x{r['lo_addr']:08X}  "
                  f"-> {kind} = 0x{r['resolved']:08X}  (into {r['reg']})")
        # Heuristic: the return register on MIPS o32/n32 is $v0. Pick the last one into v0.
        v0_refs = [r for r in refs if r["reg"] == "v0"]
        if v0_refs:
            chosen = v0_refs[-1]
            print()
            if chosen["kind"] == "load":
                print(f"[+] CAMERA_CONTROLLER_PTR_ADDR = 0x{chosen['resolved']:08X}")
                print(f"    (the helper loads *this* to get the camera controller pointer)")
            else:
                print(f"[+] CAMERA_CONTROLLER_ROOT = 0x{chosen['resolved']:08X}")
                print(f"    (the helper returns the address of this static object)")
        else:
            print("[!] No hi/lo resolved into $v0 — helper may return via a call or "
                  "compute the pointer dynamically.")
    else:
        print("[!] No hi/lo pairs found — function may be larger than expected "
              "or use a different addressing idiom.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Disassemble 0x011E7778 and resolve camera root")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_SLOT)
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=DEFAULT_FUNC_ADDR)
    ap.add_argument("--length", type=lambda s: int(s, 0), default=DEFAULT_READ_LEN)
    args = ap.parse_args(argv)

    try:
        return run(args.host, args.port, args.addr, args.length)
    except (ConnectionRefusedError,) as e:
        print(f"[!] Could not connect to PCSX2 PINE: {e}")
        return 2
    except PineError as e:
        print(f"[!] PINE error: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
