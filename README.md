# agent-loop-detector

An offline detector for loop pathologies in recorded agent trajectories: stasis (the same step emitted over and over), exact repeats within a sliding window, and oscillation cycles (A,B,A,B,…), each finding paired with a circuit-breaker suggestion. Analyze after the fact — no runtime hooking. Pure standard library, single file, offline. *Adjacent to runtime anti-loop toolkits, not equivalent to them.*

## Problem

Agents get stuck: the same tool call with the same arguments fires 40 times, or two tools take turns failing, and the only signal today is the token bill. Runtime guards can catch this live, but CI pipelines, replay harnesses, and postmortems need the reverse direction — take a trajectory JSON that already happened and answer "did it loop, where, and should the runner have halted?" No standalone checker covers that offline analysis surface.

## How it works

Input is a trajectory: `{"steps": [{"turn": 1, "tool": "search", "args": {...}, "output_digest": "…"}]}` (or a bare list; `output` text is hashed with SHA-1 when no digest is given). Each step reduces to a canonical signature — tool + key-sorted args + output digest — so turn numbers and irrelevant fields never affect matching. Three detectors run over the signatures:

- **STASIS (error)** — one identical signature repeated `--stasis-run` times consecutively → suggestion: `halt`;
- **EXACT_REPEAT (warning)** — a signature appearing `--repeat-threshold` times inside a `--window`-step sliding window → suggestion: `backoff`;
- **CYCLE (error)** — a period-L oscillation hit three times inside the window (A,B,A,B,A minimum) → suggestion: `halt`.

`suggest_breaker` collapses findings into one recommendation (`halt` / `backoff` / `none`). Exit `1` when any finding exists, `2` on usage/input errors. Reports are text or `--json`.

## How this differs from LoopBuster

[LoopBuster](https://github.com/liuchunwei732-cmyk/loopbuster) is a runtime anti-loop toolkit — its README's hook is *"Break the infinite loops of your AI Agents. Stop burning tokens on dead-ends"*, and its feature set (multi-factor similarity scoring, budget ceilings, pre-flight circuit breaker, framework guard nodes) all execute *inside* the agent loop, interleaved with the LLM calls it polices. This repo occupies the other side of that boundary: it never sits in the loop, scores nothing with fuzzy similarity, and holds no runtime state — it takes a completed (or streamed-and-recorded) trajectory and produces a deterministic, replayable verdict with exact turns and periods, suitable for CI gates on replay suites and incident postmortems. The two compose: LoopBuster halts the run; this tool audits the run.

## Quickstart

```console
$ python agent_loop_detector.py check traj.json            # ~0.1 s
analyzed 12 step(s), 2 finding(s); breaker: halt (stasis or cycle detected)
STASIS      turns=[7, 11] identical step repeated 5 times — halt: agent is stuck
```

Analyzing a 10,000-step trajectory takes 0.04 s [Measured] (see Performance).

## Why not X

- **LoopBuster** (the anchor above) — runtime guards with similarity scoring and live circuit breakers; requires embedding in the agent loop, and its verdicts are threshold-fuzzy rather than replayable static analysis.
- **Framework debug UIs (LangSmith, AgentOps traces)** — great dashboards, but loop judgment is left to a human scrolling a trace; no rule-based STASIS/CYCLE/EXACT_REPEAT classification or exit-code contract.
- **Token-budget stop conditions** — stop the bleeding but cannot distinguish "expensive productive work" from "stuck"; this tool classifies *why* a run went sideways.
- **grep over logs** — catches exact-duplicate lines; blind to key-order changes in args and to periodic cycles spanning different tools.

## Performance

All numbers [Measured] locally (Python 3.13, Windows 10, single core):

| Workload | Result | Command |
|---|---|---|
| 10,000-step synthetic trajectory | 0.04 s (~250k steps/s) | `python agent_loop_detector.py bench --steps 10000` |
| Typical 50-step replay check | <1 ms | `python agent_loop_detector.py check traj.json` |

`bench` builds a deterministic two-signature alternating trajectory and times only detection.

## Minimal Fallback

Without this tool: pipe your trajectory log through `sort | uniq -c | sort -rn | head` and eyeball repeated tool+args lines. You lose stasis run-length semantics, cycle (period) detection, key-order-insensitive arg normalization, and the exit-code contract — but a top-10 repeat count alone catches the most common "same call 40 times" failure.

## Design Trade-offs

- **Exact signatures, no fuzzy similarity.** Two calls differing by one timestamp are different steps; fuzzy matching would need embeddings (network, latency, false positives). The `output_digest` field is the escape hatch: deduplicate upstream if you want coarser grains.
- **Findings, not interventions.** The tool suggests `halt`/`backoff` but never acts — enforcement belongs to the runner, keeping this usable in postmortems where acting is wrong.
- **Window-bounded cycle detection.** Cycles longer than `--window` are invisible; the default (6) keeps O(n·window) cost predictable on huge trajectories.
- **Turn numbers are advisory.** They come from the record (or fall back to index) and are for humans; matching uses signatures only.

## Limits & Second-order Effects

- Semantic loops (paraphrased prompts, LLM-output-only variation) produce distinct signatures and are invisible; only structural repetition is caught.
- Deterministic-but-legitimate repetition (batch processing 500 similar items) trips EXACT_REPEAT; tune `--repeat-threshold` per workload or expect noise.
- Once wired into CI, a clean verdict may be over-trusted — a "no loops" run can still be wasteful in ways signatures cannot see.
- Digest-grain choices propagate: upstream systems that pre-hash outputs coarsely (e.g. status-code-only) will mask real loops.

## FAQ

**When NOT to use this?** If you need to *stop* a live agent mid-loop, use a runtime guard — this tool sees the trajectory only after steps happen. Also skip it for human-in-the-loop sessions where every step is manually approved; stasis there is the operator's choice, not a pathology.

**Why is EXACT_REPEAT a warning but STASIS/CYCLE errors?** Scattered repeats may be legitimate retries; consecutive stasis and periodic oscillation are almost never productive and burn budget linearly.

**What if my agent repeats a call but outputs differ every time?** By design that is not a loop here — vary the digest grain (e.g. hash only the status field) upstream if you want it caught.

**Does it call the network or run my steps?** No. It reads one JSON file and prints findings; nothing is executed, fetched, or sent.

## [Core Assumptions]

1. Structural repetition (identical tool + args + output) is a high-precision loop signal even though it misses semantic loops.
2. Trajectories can be captured as JSON step lists — most orchestration frameworks can dump this today.
3. Halt-worthy pathologies (stasis, short cycles) are distinguishable from legitimate retries by run structure alone, without semantic understanding.
4. Replay suites and postmortems, not live agents, are the primary consumption surface for a verdict with an exit code.

Confidence: High (≥80%) for the three detectors' mechanics and determinism (pure static analysis, fully testable); Medium (60-79%) for real-world precision on noisy production trajectories and the default thresholds. As of 2026-10-13.

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 105 purpose-built AI-engineering tools across neglected niches.

Related tools: [agent-permission-audit](https://github.com/chenhz01/agent-permission-audit) · [agent-trace-compression](https://github.com/chenhz01/agent-trace-compression) · [memory-expiry-policy](https://github.com/chenhz01/memory-expiry-policy)
