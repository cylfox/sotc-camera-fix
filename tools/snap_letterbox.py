"""Capture EE memory continuously across a cinematic letterbox fade-in.

Trigger a cinematic during the capture window. Anything that ramps
smoothly from one value to another over a few samples — and is plausible
as a letterbox alpha (small float in [0, ~1.5]) — is a candidate for
the bar-alpha animator.

Usage:
  1. Load a save right before a cinematic trigger.
  2. Run this script (it gives you a 2 s arming window before capturing).
  3. During the capture window, trigger the cinematic.
  4. Hold still until the bars are fully visible.
  5. Wait for the report.

Tunables: REGIONS, DURATION_S.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

REGIONS = [
    (0x01060000, 0x10000, "camera/state page (incl. 0x0106C880 cinematic flag)"),
    (0x01C18000, 0x08000, "live camera controller / render-side"),
    (0x01D00000, 0x10000, "render state (speculative)"),
]

DURATION_S = 6.0   # total capture window after arming
ARM_S = 2.0        # warm-up before capture starts


def capture():
    snapshots = []
    timestamps = []
    with PineClient() as pc:
        print(f"[*] Arming. Trigger the cinematic in ~{ARM_S:.0f}s.")
        time.sleep(ARM_S)
        print(f"[*] Capturing for {DURATION_S:.1f}s. GO.")
        t0 = time.monotonic()
        while time.monotonic() - t0 < DURATION_S:
            snap = {}
            ts = time.monotonic() - t0
            for base, size, _ in REGIONS:
                snap[base] = pc.read_bytes(base, size)
            snapshots.append(snap)
            timestamps.append(ts)
        print(f"[*] {len(snapshots)} snapshots captured "
              f"({len(snapshots)/DURATION_S:.1f} Hz)")
    return snapshots, timestamps


def is_plausible_alpha(values_f):
    """A letterbox alpha sits in roughly [0, 1.5], with the fade reaching
    ~1.0 at the end. Permit some slop for non-normalized impls."""
    if any(v != v for v in values_f):  # NaN
        return False
    if any(abs(v) > 5.0 for v in values_f):
        return False
    if max(values_f) - min(values_f) < 0.05:
        return False  # too small a swing
    return True


def is_monotonic(vals, tolerance=0.0):
    """Tolerant monotonic check — allows tiny noise."""
    inc = all(vals[i+1] >= vals[i] - tolerance for i in range(len(vals)-1))
    dec = all(vals[i+1] <= vals[i] + tolerance for i in range(len(vals)-1))
    return inc or dec


def has_transition(vals):
    """True if there's a clear early-period and late-period with the
    middle bridging them. Heuristic: the change between the first 25%
    and last 25% of samples is the bulk of the total swing."""
    n = len(vals)
    if n < 6:
        return False
    early = vals[: max(1, n // 4)]
    late = vals[-max(1, n // 4):]
    swing = abs(sum(late) / len(late) - sum(early) / len(early))
    total_swing = max(vals) - min(vals)
    if total_swing < 1e-6:
        return False
    return swing >= 0.6 * total_swing


def analyze(snapshots, timestamps):
    n = len(snapshots)
    print(f"\n[*] Analyzing {n} samples\n")
    candidates = []

    for base, size, desc in REGIONS:
        for off in range(0, size, 4):
            addr = base + off
            vals_u32 = [
                struct.unpack_from("<I", s[base], off)[0] for s in snapshots
            ]
            if all(v == vals_u32[0] for v in vals_u32):
                continue

            vals_f = [
                struct.unpack("<f", struct.pack("<I", u))[0] for u in vals_u32
            ]
            if not is_plausible_alpha(vals_f):
                continue
            if not is_monotonic(vals_f, tolerance=0.02):
                continue
            if not has_transition(vals_f):
                continue

            v0, v1 = vals_f[0], vals_f[-1]
            swing = v1 - v0
            candidates.append((addr, v0, v1, swing, vals_f, desc))

    # Score: prefer swings ~1.0 (typical alpha 0->1), but accept anything
    # plausible. Sort by closeness of swing magnitude to 1.0, then by
    # absolute swing.
    candidates.sort(key=lambda c: (abs(abs(c[3]) - 1.0), -abs(c[3])))
    return candidates


def fmt_series(vals, n_show=8):
    if len(vals) <= n_show:
        return " ".join(f"{v:+.3f}" for v in vals)
    step = max(1, len(vals) // n_show)
    sampled = vals[::step][:n_show]
    return " ".join(f"{v:+.3f}" for v in sampled)


def main():
    snapshots, timestamps = capture()
    cands = analyze(snapshots, timestamps)
    print(f"[*] {len(cands)} candidates passed alpha-fade filter\n")
    print("=== Top 40 (sorted by closeness of swing to 1.0) ===")
    for addr, v0, v1, swing, series, desc in cands[:40]:
        print(
            f"  0x{addr:08X}  start={v0:+.4f}  end={v1:+.4f}  swing={swing:+.4f}"
            f"  [{desc}]"
        )
        print(f"             series: {fmt_series(series)}")


if __name__ == "__main__":
    main()
