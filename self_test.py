# -*- coding: utf-8 -*-
"""self_test for agent-loop-detector — inherits scaffold v2 four defenses:
  D1 SystemExit/BaseException capture in run_cli
  D2 Unicode-safe patterns (CJK/emoji fixtures)
  D3 fixtures written with newline="" (Windows CRLF safe)
  D4 last line `SUMMARY: PASS n/n`
"""
import contextlib, io, json, os, sys, tempfile, unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib
mod = importlib.import_module("agent_loop_detector")
main = mod.main


def run_cli(argv):
    """D1: catch SystemExit and Exception; return (code, stdout, stderr)."""
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            main(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        code = 1
        buf_err.write(repr(e))
    return code, buf_out.getvalue(), buf_err.getvalue()


def _write(text, suffix=".json"):
    """D3: newline="" prevents \r\n double-write on Windows."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


def _step(t, tool="search", q="x", digest="aaa"):
    return {"turn": t, "tool": tool, "args": {"q": q}, "output_digest": digest}


def _traj(*steps):
    return json.dumps({"steps": list(steps)})


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


# ---------------- [A] functional ----------------

@case
def a01_clean_trajectory_exit0():
    p = _write(_traj(_step(1, q="a", digest="d1"), _step(2, q="b", digest="d2"),
                     _step(3, q="c", digest="d3")))
    code, out, _ = run_cli(["check", p])
    assert code == 0 and "0 finding" in out


@case
def a02_stasis_detected():
    p = _write(_traj(_step(1), _step(2), _step(3)))
    code, out, _ = run_cli(["check", p])
    assert code == 1 and "STASIS" in out


@case
def a03_exact_repeat_detected():
    steps = [_step(1, q="a", digest="d1"), _step(2, q="b", digest="d2"),
             _step(3, q="a", digest="d1"), _step(4, q="b", digest="d2"),
             _step(5, q="a", digest="d1")]
    p = _write(_traj(*steps))
    code, out, _ = run_cli(["check", p])
    assert code == 1 and "EXACT_REPEAT" in out


@case
def a04_cycle_detected():
    steps = [_step(1, tool="a", digest="d1"), _step(2, tool="b", digest="d2"),
             _step(3, tool="a", digest="d1"), _step(4, tool="b", digest="d2"),
             _step(5, tool="a", digest="d1"), _step(6, tool="b", digest="d2")]
    p = _write(_traj(*steps))
    code, out, _ = run_cli(["check", p])
    assert code == 1 and "CYCLE" in out


@case
def a05_breaker_halt_on_stasis():
    f = mod.detect([_step(i) for i in range(4)])
    b = mod.suggest_breaker(f)
    assert b["action"] == "halt"


@case
def a06_breaker_backoff_on_repeats():
    steps = [_step(1, digest="d1"), _step(2, digest="d2"), _step(3, digest="d3"),
             _step(4, digest="d1"), _step(5, digest="d4"), _step(6, digest="d1")]
    f = mod.detect(steps)
    assert any(x["type"] == "EXACT_REPEAT" for x in f)
    assert not any(x["type"] in ("CYCLE", "STASIS") for x in f)
    assert mod.suggest_breaker(f)["action"] == "backoff"


@case
def a07_breaker_none_when_clean():
    f = mod.detect([_step(i, q="q%d" % i, digest="d%d" % i) for i in range(5)])
    assert mod.suggest_breaker(f)["action"] == "none"


@case
def a08_normalize_step_deterministic():
    s1 = mod.normalize_step(_step(1, q="hello"))
    s2 = mod.normalize_step(_step(9, q="hello"))
    assert s1 == s2  # turn number does not affect the signature


@case
def a09_args_order_irrelevant():
    s1 = mod.normalize_step({"tool": "t", "args": {"a": 1, "b": 2}, "output_digest": "d"})
    s2 = mod.normalize_step({"tool": "t", "args": {"b": 2, "a": 1}, "output_digest": "d"})
    assert s1 == s2


@case
def a10_sha_fallback_for_output_text():
    s = mod.normalize_step({"tool": "t", "args": {}, "output": "hello world"})
    assert "|" in s and len(s.split("|")[2]) == 12


@case
def a11_stasis_run_threshold_custom():
    steps = [_step(i) for i in range(3)]  # run of 3
    assert not any(f["type"] == "STASIS" for f in mod.detect(steps, stasis_run=4))
    assert any(f["type"] == "STASIS" for f in mod.detect(steps, stasis_run=3))


@case
def a12_repeat_threshold_custom():
    steps = [_step(1, digest="d1"), _step(2, digest="d2"), _step(3, digest="d1")]
    assert not any(f["type"] == "EXACT_REPEAT" for f in mod.detect(steps, repeat_threshold=3))
    assert any(f["type"] == "EXACT_REPEAT" for f in mod.detect(steps, repeat_threshold=2))


@case
def a13_window_narrows_detection():
    steps = [_step(1, digest="d1"), _step(2, digest="d2"), _step(3, digest="d1"),
             _step(4, digest="d2"), _step(5, digest="d1"), _step(6, digest="d9")]
    wide = mod.detect(steps, window=6, repeat_threshold=3)
    narrow = mod.detect(steps, window=3, repeat_threshold=3)
    assert any(f["type"] == "EXACT_REPEAT" for f in wide)
    assert not any(f["type"] == "EXACT_REPEAT" for f in narrow)


@case
def a14_check_json_structure():
    p = _write(_traj(_step(1), _step(2), _step(3)))
    code, out, _ = run_cli(["check", p, "--json"])
    data = json.loads(out)
    assert data["steps"] == 3 and data["breaker"]["action"] == "halt"


@case
def a15_bench_small():
    code, out, _ = run_cli(["bench", "--steps", "100"])
    assert code == 0 and "steps=100" in out


@case
def a16_bench_default():
    code, out, _ = run_cli(["bench"])
    assert code == 0 and "steps/s" in out


@case
def a17_help_exit0():
    code, out, _ = run_cli(["--help"])
    assert code == 0 and "agent-loop-detector" in out


@case
def a18_no_args_exit2():
    code, _, _ = run_cli([])
    assert code == 2


@case
def a19_unknown_subcommand_exit2():
    code, _, _ = run_cli(["spin"])
    assert code == 2


@case
def a20_list_form_trajectory_accepted():
    p = _write(json.dumps([_step(1), _step(2), _step(3)]))
    code, out, _ = run_cli(["check", p])
    assert code == 1 and "STASIS" in out


@case
def a21_turn_numbers_fall_back_to_index():
    steps = [{"tool": "t", "args": {}, "output_digest": "d"} for _ in range(3)]
    f = mod.detect(steps)
    assert f[0]["turns"][0] == 1


@case
def a22_dedup_repeat_signatures():
    steps = [_step(i, digest="d1") for i in range(10)]  # one giant stasis run
    f = mod.detect(steps)
    types = [x["type"] for x in f]
    assert types.count("STASIS") == 1  # one run reported once


@case
def a23_cycle_period_reported():
    steps = [_step(1, tool="a", digest="d1"), _step(2, tool="b", digest="d2"),
             _step(3, tool="a", digest="d1"), _step(4, tool="b", digest="d2"),
             _step(5, tool="a", digest="d1"), _step(6, tool="b", digest="d2")]
    f = mod.detect(steps)
    cyc = [x for x in f if x["type"] == "CYCLE"][0]
    assert cyc["period"] == 2


# ---------------- [B] exception paths ----------------

@case
def b01_missing_file():
    code, _, err = run_cli(["check", "Z:/no/traj.json"])
    assert code == 1 and "cannot read" in err


@case
def b02_invalid_json():
    p = _write("{nope")
    code, _, err = run_cli(["check", p])
    assert code == 1 and "invalid JSON" in err


@case
def b03_scalar_trajectory_rejected():
    p = _write("42")
    code, _, err = run_cli(["check", p])
    assert code == 1 and "must be a list" in err


@case
def b04_object_without_steps_rejected():
    p = _write('{"turns": []}')
    code, _, err = run_cli(["check", p])
    assert code == 1 and "must be a list" in err


@case
def b05_steps_not_list():
    p = _write('{"steps": {"a": 1}}')
    code, _, err = run_cli(["check", p])
    assert code == 1 and "must be a list" in err


@case
def b06_step_not_object_tolerated():
    p = _write('{"steps": [7, 7, 7]}')
    code, out, _ = run_cli(["check", p])
    assert code == 1 and "STASIS" in out  # identical reprs -> stasis


@case
def b07_window_zero_rejected():
    p = _write(_traj(_step(1)))
    code, _, _ = run_cli(["check", p, "--window", "0"])
    assert code == 2


@case
def b08_repeat_threshold_zero_rejected():
    p = _write(_traj(_step(1)))
    code, _, _ = run_cli(["check", p, "--repeat-threshold", "0"])
    assert code == 2


@case
def b09_stasis_run_negative_rejected():
    p = _write(_traj(_step(1)))
    code, _, _ = run_cli(["check", p, "--stasis-run", "-1"])
    assert code == 2


@case
def b10_window_not_int():
    p = _write(_traj(_step(1)))
    code, _, _ = run_cli(["check", p, "--window", "big"])
    assert code == 2


@case
def b11_bench_steps_zero():
    code, _, _ = run_cli(["bench", "--steps", "0"])
    assert code == 2


@case
def b12_bench_steps_negative():
    code, _, _ = run_cli(["bench", "--steps", "-3"])
    assert code == 2


@case
def b13_bench_steps_not_int():
    code, _, _ = run_cli(["bench", "--steps", "lots"])
    assert code == 2


@case
def b14_empty_trajectory_ok():
    p = _write('{"steps": []}')
    code, out, _ = run_cli(["check", p])
    assert code == 0 and "0 finding" in out


@case
def b15_empty_file():
    p = _write("")
    code, _, _ = run_cli(["check", p])
    assert code == 1


@case
def b16_whitespace_only():
    p = _write(" \n ")
    code, _, _ = run_cli(["check", p])
    assert code == 1


@case
def b17_args_not_serializable_tolerated():
    p = _write('{"steps": [{"turn": 1, "tool": "t", "args": {"f": 1.5}, "output_digest": "d"}]}')
    code, out, _ = run_cli(["check", p])
    assert code == 0


@case
def b18_output_digest_non_string_tolerated():
    p = _write('{"steps": [{"turn": 1, "tool": "t", "args": {}, "output_digest": 7}]}')
    code, out, _ = run_cli(["check", p])
    assert code == 0  # falls back to hashing output (missing -> digest of null)


@case
def b19_directory_as_input():
    code, _, err = run_cli(["check", os.path.dirname(os.path.abspath(__file__))])
    assert code == 1 and "cannot read" in err


@case
def b20_tool_missing_defaults_empty():
    s1 = mod.normalize_step({"args": {}, "output_digest": "d"})
    s2 = mod.normalize_step({"tool": "", "args": {}, "output_digest": "d"})
    assert s1 == s2


# ---------------- [C] extreme / edge ----------------

@case
def c01_unicode_cjk_args():
    steps = [_step(i, q="查询中文第%d次" % i, digest="d%d" % i) for i in range(1, 4)]
    p = _write(_traj(*steps))
    code, out, _ = run_cli(["check", p])
    assert code == 0 and "0 finding" in out  # D2: CJK survives normalization


@case
def c02_unicode_cjk_loop_detected():
    steps = [_step(i, q="重试同一个查询", digest="same") for i in range(1, 5)]
    p = _write(_traj(*steps))
    code, out, _ = run_cli(["check", p])
    assert code == 1 and "STASIS" in out


@case
def c03_emoji_output_digest():
    steps = [_step(i, digest="\U0001f600-\U0001f601" * 3) for i in range(4)]
    f = mod.detect(steps)
    assert any(x["type"] == "STASIS" for x in f)


@case
def c04_two_step_trajectory_no_cycle():
    steps = [_step(1, tool="a", digest="d1"), _step(2, tool="b", digest="d2")]
    f = mod.detect(steps)
    assert not any(x["type"] == "CYCLE" for x in f)


@case
def c05_minimum_oscillation_needs_three_hits():
    steps = [_step(1, tool="a", digest="d1"), _step(2, tool="b", digest="d2"),
             _step(3, tool="a", digest="d1"), _step(4, tool="b", digest="d2")]
    f = mod.detect(steps)  # A,B,A,B = only two A hits at period 2... plus repeats
    cyc = [x for x in f if x["type"] == "CYCLE"]
    assert cyc == []  # three period hits required (A,B,A,B,A minimum)


@case
def c06_minimum_true_oscillation():
    steps = [_step(1, tool="a", digest="d1"), _step(2, tool="b", digest="d2"),
             _step(3, tool="a", digest="d1"), _step(4, tool="b", digest="d2"),
             _step(5, tool="a", digest="d1"), _step(6, tool="b", digest="d2")]
    f = mod.detect(steps)
    assert any(x["type"] == "CYCLE" for x in f)


@case
def c07_huge_trajectory_10k():
    steps = [_step(i, q="q%d" % (i % 1000), digest="d%d" % (i % 997)) for i in range(1, 10001)]
    p = _write(_traj(*steps))
    code, out, _ = run_cli(["check", p])
    assert code in (0, 1) and "finding" in out


@case
def c08_long_args_10k_chars():
    p = _write(_traj(_step(1, q="x" * 10000, digest="d1"),
                     _step(2, q="y" * 10000, digest="d2"),
                     _step(3, q="z" * 10000, digest="d3")))
    code, out, _ = run_cli(["check", p])
    assert code == 0


@case
def c09_window_larger_than_trajectory():
    steps = [_step(1, digest="d1"), _step(2, digest="d1"), _step(3, digest="d1")]
    f = mod.detect(steps, window=100)
    assert any(x["type"] == "STASIS" for x in f)


@case
def c10_utf8_bom_trajectory():
    fd, p = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(p, "wb") as fh:
        fh.write(b"\xef\xbb\xbf" + _traj(_step(1), _step(2)).encode("utf-8"))
    code, out, _ = run_cli(["check", p])
    assert code == 0


@case
def c11_crlf_file():
    fd, p = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(p, "w", encoding="utf-8", newline="") as fh:  # D3
        fh.write(_traj(_step(1), _step(2)).replace("\n", "\r\n"))
    code, out, _ = run_cli(["check", p])
    assert code == 0


@case
def c12_action_key_fallback():
    s1 = mod.normalize_step({"action": "click", "args": {}, "output_digest": "d"})
    s2 = mod.normalize_step({"tool": "click", "args": {}, "output_digest": "d"})
    assert s1 == s2


@case
def c13_extra_step_keys_ignored():
    s1 = mod.normalize_step({"tool": "t", "args": {}, "output_digest": "d", "latency_ms": 5})
    s2 = mod.normalize_step({"tool": "t", "args": {}, "output_digest": "d"})
    assert s1 == s2


@case
def c14_stasis_of_50_reported_once():
    steps = [_step(i) for i in range(1, 51)]
    f = mod.detect(steps)
    assert [x for x in f if x["type"] == "STASIS"][0]["turns"][1] == 50


@case
def c15_interleaved_noise_no_false_stasis():
    steps = [_step(i, q="q%d" % i, digest="d%d" % i) for i in range(20)]
    f = mod.detect(steps)
    assert f == []


@case
def c16_breaker_suggestion_shape():
    b = mod.suggest_breaker([])
    assert set(b) == {"action", "reason"}


@case
def c17_nested_args_sorted_canonically():
    s1 = mod.normalize_step({"tool": "t", "args": {"x": {"b": 1, "a": 2}}, "output_digest": "d"})
    s2 = mod.normalize_step({"tool": "t", "args": {"x": {"a": 2, "b": 1}}, "output_digest": "d"})
    assert s1 == s2


@case
def c18_period_up_to_window_half():
    steps = []
    for i in range(1, 13):
        tool = "t%d" % (i % 4)
        steps.append(_step(i, tool=tool, digest="d%d" % (i % 4)))
    f = mod.detect(steps, window=12)
    assert any(x["type"] == "CYCLE" and x["period"] in (2, 3, 4) for x in f)


@case
def c19_float_turn_values_tolerated():
    p = _write('{"steps": [{"turn": 1.0, "tool": "t", "args": {}, "output_digest": "d"},'
               '{"turn": 2.0, "tool": "t", "args": {}, "output_digest": "d"},'
               '{"turn": 3.0, "tool": "t", "args": {}, "output_digest": "d"}]}')
    code, out, _ = run_cli(["check", p])
    assert code == 1 and "STASIS" in out


@case
def c20_null_output_digest_hashes_output():
    s1 = mod.normalize_step({"tool": "t", "args": {}, "output": None})
    s2 = mod.normalize_step({"tool": "t", "args": {}, "output": None, "turn": 5})
    assert s1 == s2


class T(unittest.TestCase):
    def test_meta_case_count(self):
        self.assertGreaterEqual(len(CASES), 60)


for _fn in CASES:
    setattr(T, "test_" + _fn.__name__, lambda self, f=_fn: f())

if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    total, fails = r.testsRun, len(r.failures) + len(r.errors)
    print("SUMMARY: PASS %d/%d" % (total - fails, total))
    sys.exit(0 if fails == 0 else 1)
