#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent-loop-detector — offline analysis of an agent trajectory for loop
pathologies: stasis (identical steps repeated), exact repeats in a window,
and oscillation cycles (A,B,A,B...), with a circuit-breaker suggestion.

This is an offline trajectory checker, NOT a runtime guard: it analyzes a
recorded or streamed step list after the fact. Runtime toolkits (e.g.
LoopBuster) sit inside the agent loop; this tool sits in CI, replay, and
postmortem pipelines. Pure standard library, single file, offline.
"""
import argparse, hashlib, json, re, sys, time


def normalize_step(step, digest_len=12):
    """Canonical signature for a step: tool + sorted args + output digest."""
    if not isinstance(step, dict):
        return repr(step)
    tool = str(step.get("tool", step.get("action", "")))
    args = step.get("args", {})
    try:
        args_s = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        args_s = repr(args)
    out = step.get("output_digest")
    if not isinstance(out, str) or not out:
        raw = json.dumps(step.get("output"), sort_keys=True, ensure_ascii=False, default=str)
        out = hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:digest_len]
    return "%s|%s|%s" % (tool, args_s, out[:digest_len])


def detect(steps, window=6, repeat_threshold=3, stasis_run=3):
    """Detect loop pathologies. Returns findings with turns and suggestions."""
    findings = []
    sigs = [normalize_step(s) for s in steps]
    turns = [s.get("turn", i + 1) if isinstance(s, dict) else i + 1
             for i, s in enumerate(steps)]

    # stasis: identical signature repeated consecutively
    run_start = 0
    for i in range(1, len(sigs) + 1):
        if i == len(sigs) or sigs[i] != sigs[run_start]:
            if i - run_start >= stasis_run:
                findings.append({
                    "type": "STASIS", "severity": "error",
                    "turns": [turns[run_start], turns[i - 1]],
                    "detail": "identical step repeated %d times" % (i - run_start),
                    "suggestion": "halt: agent is stuck emitting the same step"})
            run_start = i

    # exact repeats within sliding windows
    reported = set()
    for i in range(len(sigs)):
        w = sigs[i:i + window]
        for sig in set(w):
            if w.count(sig) >= repeat_threshold and sig not in reported:
                reported.add(sig)
                hit_turns = [turns[j] for j in range(i, min(i + window, len(sigs)))
                             if sigs[j] == sig]
                findings.append({
                    "type": "EXACT_REPEAT", "severity": "warning",
                    "turns": hit_turns[:repeat_threshold],
                    "detail": "signature repeated %d times within a %d-step window"
                              % (w.count(sig), window),
                    "suggestion": "backoff: raise repeat threshold or vary the prompt"})

    # oscillation: period-L cycle hit three times inside a window
    for L in range(2, max(3, window // 2) + 1):
        for i in range(len(sigs) - 2 * L):
            if (sigs[i] == sigs[i + L] == sigs[i + 2 * L]
                    and sigs[i] != sigs[i + 1]):
                findings.append({
                    "type": "CYCLE", "severity": "error", "period": L,
                    "turns": [turns[i], turns[i + L], turns[i + 2 * L]],
                    "detail": "period-%d oscillation detected" % L,
                    "suggestion": "halt: breaking the cycle needs intervention, not retries"})
                break
        else:
            continue
        break
    return findings


def suggest_breaker(findings):
    """Map findings to a single circuit-breaker recommendation."""
    if not findings:
        return {"action": "none", "reason": "no loop pathologies detected"}
    if any(f["type"] in ("STASIS", "CYCLE") for f in findings):
        return {"action": "halt", "reason": "stasis or cycle detected; retrying burns tokens"}
    return {"action": "backoff", "reason": "repeats detected; vary inputs or raise thresholds"}


def _load(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _steps_of(doc):
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict) and isinstance(doc.get("steps"), list):
        return doc["steps"]
    return None


def _positive_int(text):
    try:
        v = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("not an integer: %r" % text)
    if v < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return v


def bench(n):
    steps = [{"turn": i, "tool": "search", "args": {"q": "same"},
              "output_digest": "d%03d" % (i % 2)} for i in range(n)]
    t0 = time.perf_counter()
    f = detect(steps)
    dt = time.perf_counter() - t0
    return n, len(f), dt


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="agent-loop-detector",
        description="Detect loop pathologies in a recorded agent trajectory (offline).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="analyze a trajectory file")
    pc.add_argument("trajectory")
    pc.add_argument("--window", type=_positive_int, default=6)
    pc.add_argument("--repeat-threshold", type=_positive_int, default=3)
    pc.add_argument("--stasis-run", type=_positive_int, default=3)
    pc.add_argument("--json", action="store_true")

    pb = sub.add_parser("bench", help="time detection on a synthetic trajectory")
    pb.add_argument("--steps", type=_positive_int, default=10000)

    args = ap.parse_args(argv)
    if args.cmd == "bench":
        n, k, dt = bench(args.steps)
        print("steps=%d findings=%d in %.4fs (%.0f steps/s)"
              % (n, k, dt, n / dt if dt else 0))
        sys.exit(0)

    try:
        doc = _load(args.trajectory)
    except OSError as exc:
        print("error: cannot read %s: %s" % (args.trajectory, exc), file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print("error: invalid JSON in %s: %s" % (args.trajectory, exc), file=sys.stderr)
        sys.exit(1)

    steps = _steps_of(doc)
    if steps is None:
        print("error: trajectory must be a list of steps or {\"steps\": [...]}", file=sys.stderr)
        sys.exit(1)

    findings = detect(steps, args.window, args.repeat_threshold, args.stasis_run)
    breaker = suggest_breaker(findings)
    if args.json:
        print(json.dumps({"steps": len(steps), "findings": findings,
                          "breaker": breaker}, ensure_ascii=False, indent=2))
    else:
        print("analyzed %d step(s), %d finding(s); breaker: %s (%s)"
              % (len(steps), len(findings), breaker["action"], breaker["reason"]))
        for f in findings:
            print("%-12s turns=%s %s — %s"
                  % (f["type"], f["turns"], f["detail"], f["suggestion"]))
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
