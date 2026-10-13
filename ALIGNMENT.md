# Alignment Audit — agent-loop-detector

Round R14, rubric v4.0 (E/F graded). Local-only draft: no git remote, no push, no repo creation.
Date: 2026-10-13.

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Runnable Python, pure stdlib | PASS | agent_loop_detector.py imports argparse/hashlib/json/sys/time only; `python agent_loop_detector.py --help` runs |
| 2 | argparse CLI | PASS | subcommands check/bench with --window/--repeat-threshold/--stasis-run/--json; usage errors exit 2 |
| 3 | self_test inherits scaffold-v2 four defenses | PASS | D1 SystemExit caught in run_cli; D2 CJK/emoji fixtures (c01–c03); D3 fixtures via newline="" (c11, _write); D4 last line `SUMMARY: PASS n/n` |
| 4 | E gate >=60 cases, 3 categories | PASS | SUMMARY: PASS 64/64 — [A] 23 functional / [B] 20 exception / [C] 20 extreme edge, incl. empty/oversized/unicode/BOM/CRLF inputs |
| 5 | SUMMARY last-line contract | PASS | `python self_test.py` prints `SUMMARY: PASS 64/64` as final line; meta-case asserts len(CASES)>=60 |
| 6 | README English, <=60-word lead | PASS | README.md opening paragraph is 57 words, English |
| 7 | README Problem section | PASS | README.md '## Problem' |
| 8 | README How-it-works | PASS | README.md '## How it works' (three detectors + breaker) |
| 9 | README Quickstart with timing | PASS | README.md '## Quickstart' cites run times |
| 10 | why-not-X >=3 alternatives | PASS | README.md '## Why not X' lists 4 alternatives incl. the real anchor LoopBuster; adjacent per _r14_design.json |
| 11 | Performance [Measured] + repro command | PASS | README.md '## Performance' table with `python agent_loop_detector.py bench --steps 10000` repro command |
| 12 | Minimal Fallback | PASS | README.md '## Minimal Fallback' (sort/uniq -c pipeline) |
| 13 | Design Trade-offs | PASS | README.md '## Design Trade-offs' (4 entries) |
| 14 | Limits & Second-order Effects | PASS | README.md '## Limits & Second-order Effects' (4 entries) |
| 15 | FAQ incl When NOT to use | PASS | README.md '## FAQ' first item is 'When NOT to use this?' |
| 16 | Core Assumptions >=3 + confidence + as-of + hygiene | PASS | README.md '[Core Assumptions]' lists 4 assumptions with confidence line and 'As of 2026-10-13'; MIT LICENSE (zhengming contributors); CHANGELOG.md v0.1.0 -> v0.1.1; no secrets, no real names, contact limited to hcac4735@agent.qq.com |
| F2 | Anchor README read before writing How-this-differs | PASS | `gh api -H "Accept: application/vnd.github.raw" repos/liuchunwei732-cmyk/loopbuster/readme` executed 2026-10-13; dedicated section 'How this differs from LoopBuster' quotes one sentence verbatim ("Break the infinite loops of your AI Agents. Stop burning tokens on dead-ends") — single-sentence quote, no >50-word copying; factual runtime-vs-offline framing, no disparagement |

Round-2 iterations: stasis turn-range and 1-based turn fixtures fixed; repeat-vs-cycle test
expectations aligned with detector semantics; non-object step repr handling covered; case count
raised into the 60-85 band; Performance re-measured; all suites re-run green.
