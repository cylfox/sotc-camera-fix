"""Watch the camera basis with phase markers so you know when to do what.

Timeline:
  t=0..3s:  HOLD LEFT STICK FULL LEFT
  t=3..6s:  HOLD LEFT STICK FULL RIGHT
  t=6..9s:  RELEASE (neutral)

Prints phase labels so you can align stick actions with the data.
Summarizes which phase saw the most basis change.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CONTROLLER = 0x01C180A0
BASIS_A = CONTROLLER + 0x570


def read_vec3(pc, addr):
    return (pc.read_f32(addr), pc.read_f32(addr + 4), pc.read_f32(addr + 8))


PHASES = [
    (3.0, "HOLD LEFT STICK *** FULL LEFT ***"),
    (3.0, "HOLD LEFT STICK *** FULL RIGHT ***"),
    (3.0, "*** RELEASE / NEUTRAL ***"),
]


with PineClient() as pc:
    print(f"[*] Basis at 0x{BASIS_A:08X}")
    print(f"[*] Get into aim mode now. Starting in 2 seconds...")
    for i in (2, 1):
        print(f"    {i}...")
        time.sleep(1)
    print()

    t0 = time.monotonic()
    phase_idx = 0
    phase_start = t0
    phase_end = phase_start + PHASES[phase_idx][0]
    print(f"=== phase 1: {PHASES[0][1]} ===")

    samples_per_phase = [[], [], []]
    last_fwd = None
    while True:
        now = time.monotonic()
        if now >= phase_end:
            phase_idx += 1
            if phase_idx >= len(PHASES):
                break
            phase_start = phase_end
            phase_end = phase_start + PHASES[phase_idx][0]
            print(f"\n=== phase {phase_idx + 1}: {PHASES[phase_idx][1]} ===")

        fwd = read_vec3(pc, BASIS_A + 0x00)
        samples_per_phase[phase_idx].append(fwd)

        if last_fwd is None or tuple(round(x, 3) for x in fwd) != tuple(round(x, 3) for x in last_fwd):
            elapsed = now - t0
            print(f"  t={elapsed:5.2f}s  fwd=({fwd[0]:+.4f}, {fwd[1]:+.4f}, {fwd[2]:+.4f})")
        last_fwd = fwd
        time.sleep(0.05)

    print("\n[*] Summary:")
    for i, (dur, label) in enumerate(PHASES):
        samples = samples_per_phase[i]
        unique = set(tuple(round(x, 4) for x in v) for v in samples)
        if len(samples) < 2:
            continue
        fwd_min_x = min(v[0] for v in samples)
        fwd_max_x = max(v[0] for v in samples)
        fwd_min_y = min(v[1] for v in samples)
        fwd_max_y = max(v[1] for v in samples)
        fwd_min_z = min(v[2] for v in samples)
        fwd_max_z = max(v[2] for v in samples)
        print(f"    phase {i+1}: {label}")
        print(f"      {len(samples)} samples, {len(unique)} unique")
        print(f"      x range: [{fwd_min_x:+.4f}, {fwd_max_x:+.4f}]  delta={fwd_max_x - fwd_min_x:.4f}")
        print(f"      y range: [{fwd_min_y:+.4f}, {fwd_max_y:+.4f}]  delta={fwd_max_y - fwd_min_y:.4f}")
        print(f"      z range: [{fwd_min_z:+.4f}, {fwd_max_z:+.4f}]  delta={fwd_max_z - fwd_min_z:.4f}")
