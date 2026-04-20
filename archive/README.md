# Archive

Scripts and raw capture data from the discovery phase. Most of these are **not part of the shipped solution** — they were used to explore the problem, rule out approaches, or validate hypotheses that didn't pan out. They're preserved here for anyone retracing the reverse-engineering process or adapting the same techniques to other games/builds.

Active tools (still useful for installing, modifying, or porting the patch) live in `../tools/`.

## Scripts

### Scanning / searching

| Script | Purpose | Outcome |
|---|---|---|
| `scan_pi2.py` | Search heap for `0x3FC90FDB` (π/2 — observed as FPR `$f03` during pitch hold) | Found only static config constants; not the live pitch scalar |
| `scan_neutral_pitch.py` | Full-EE scan for `0x4091E9F7` (4.55981 — observed as `$f04` idle value) | **Zero hits anywhere** — confirmed the neutral-pitch scalar is VU0-resident only |
| `scan_neutral_pitch.out` | Text log of the above scan run | Evidence for the negative result |
| `scan_lerp_rates.py` | Search camera-adjacent regions for common auto-focus lerp-rate floats (0.1, 0.05, etc.) | 248 hits; none were the actual auto-focus driver (hammer-tested) |
| `find_pi2_loads.py` | Scan code for `lui rX, 0x3FC9 + ori/addiu` pairs (the MIPS idiom for loading π/2) | Found 8 `lui` but zero pairs — π/2 is loaded via `lwc1` from rodata, not immediate sequences |
| `find_f3_writers.py`, `find_f3_decay.py` | Scan code for instructions writing to FPR `$f3` / decay patterns | Too many matches to triage without conditional breakpoints |
| `find_stick_copies.py` | Scan memory for copies of the pad stick bytes | Located replicas but none were writable patch points |
| `find_aim_flag.py` | Early region-diff between free-roam and aim states | Too noisy (per-frame flicker polluted results); **superseded by `../tools/find_stable_flags.py`** |

### Scenario capture / analysis

| Script | Purpose |
|---|---|
| `scenario_run.py` | Poll a memory region at ~15 Hz, save JSON snapshots. Used for idle/yaw/pitch/walk captures |
| `analyze.py` | Cross-scenario diff of idle/yaw/pitch/walk captures — per-offset change stats |
| `analyze_autofocus.py` | Phase-split analyzer: pan-phase / settled / auto-rotation |
| `analyze_pscan.py` | Analyzer for `parallel_scan.py` snapshots |
| `fast_probe.py` | High-frequency (~2300 Hz) single-connection poll of a tight region |
| `diff_holds.py` | Diff across "hold up" / "hold down" / "hold neutral" captures |

### Live-memory experiments

| Script | Purpose |
|---|---|
| `hammer_flag.py` | Continuously overwrite a candidate memory location (test if it's the auto-focus lever) |
| `poll_gates.py` | Poll multiple candidate "gate" addresses simultaneously |
| `poll_candidates.py` | Tally unique values seen at each of several addresses — rule out per-frame flicker |
| `poll_debug.py` | Poll the debug-trampoline's `$s0` / `$ra` log slots |
| `debug_trampoline.py` | Experimental trampoline that logged `$s0` and `$ra` on every pad read — used to confirm the pad-read function is mode-agnostic at the caller level |

### Disassembly

| Script | Purpose |
|---|---|
| `reverse_011E7778.py` | Capstone-based disassembly helper for the dispatch function at `0x011E7778` (initial research) |

## Raw data (`scenarios/`)

JSON captures from PINE polling. Each file contains timestamped memory snapshots for a specific scenario:

- `idle.json`, `yaw.json`, `pitch.json`, `walk.json`, `autofocus.json` — scenario_run captures
- `hold_{up,down,neutral}.json` — stick-held states
- `fast_*.json` — fast_probe captures
- `pscan_*.json` — parallel_scan captures (256 KB snapshots at ~1.7s per snap)
- `modeflag_{free,aim}.json` — early region-diff attempt
- `stable_{free,aim}.json` — the captures that found the mode flag

These are kept for reproducibility: if you want to re-run the analysis scripts or verify specific capture data, the raw inputs are here.

## Why keep these at all?

1. **Provenance.** The final solution rests on conclusions drawn from negative results (e.g., "the neutral-pitch scalar is not in EE memory"). Throwing away the scripts that produced those conclusions would leave the claims unverifiable.

2. **Reusability.** The techniques — stable-state sampling, byte-threshold binary search, free-space scanning, trampoline injection — apply to other games and other auto-behavior problems. The scripts are working examples.

3. **Future porting.** When porting to NTSC-U or the HD remaster, some of these search tools will be needed again to re-locate the equivalent addresses.
