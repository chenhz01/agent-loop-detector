# Changelog — agent-loop-detector

All releases are local drafts; no remote operations are performed.

## v0.1.1 — 2026-10-13

Fixed:
- stasis runs now report the correct turn range (first..last of the run);
  self_test fixtures aligned to 1-based turn numbers.
- cycle detector no longer re-reports the same period inside one window scan.

Changed:
- self_test expanded to 64 cases across functional / exception / extreme-edge
  categories (scaffold v2 four defenses: SystemExit capture, Unicode-safe
  matching, Windows newline-safe fixtures, SUMMARY last line); repeat-vs-cycle
  expectations tightened (alternating pairs are CYCLE, scattered repeats are
  EXACT_REPEAT only).
- README: How-this-differs section written after reading the LoopBuster README
  (gh api, 2026-10-13); Performance re-measured via shipped `bench` subcommand.

## v0.1.0 — 2026-10-13

Added:
- Initial local draft: step signature normalization (tool + sorted args +
  output digest with SHA-1 fallback), STASIS / EXACT_REPEAT / CYCLE detectors,
  circuit-breaker suggestion mapping, argparse CLI (check / bench) and
  scaffold-v2 self_test.
