#!/usr/bin/env python3
"""Measure the payload, and do not cut it yet.

A 24-agent run cost 5,345,133 tokens. Wave 1 handed its agents 852,260 bytes of
document -- about 213,000 tokens, **9.7%** of what the wave spent. Three
candidate explanations were fitted against those 24 agents and all three failed:
output tokens (R2 0.145, negative slope), tool calls (0.421), output x calls
(0.025). Every model left 166,000-262,000 per agent unexplained, and
`arbiter-B-bugs-accept` spent 398,092 tokens while writing 2,286 back.

One term was never measured: the prompt the lead composes and sends. It is built
inside the dispatch call and written nowhere, so it is invisible -- and a
subagent's prompt is re-sent on every internal turn, which makes an invisible
term the one most likely to dominate.

  D1  a payload is recorded before dispatch, by size
  D2  the ledger is append-only
  D3  the report pairs payload against spend as `payload x calls`
  D4  a size is measured; the token figure is labelled derived
  D5  the script concludes nothing -- it states no cause and cuts nothing
  D6  a missing payload is refused rather than recorded as zero

D5 is the discipline this file mostly exists for. A cap of six tool calls per
agent was proposed on the strength of a quadratic model that the data later
refused, and it would have made agents conclude early for a saving that was not
there. Making the same mistake twice -- cutting a term before sizing it -- is the
failure mode, so the script measures and says so, in those words.

D6 matters because a payload recorded as zero is worse than one not recorded: it
enters the arithmetic as evidence that the prompt is small.

Run:  python3 skills/spec-recon/tests/test_dispatch_log.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, "scripts", "dispatch_log.py")
MODEL = os.path.join(ROOT, "skills", "spec-recon", "references", "cost-model.md")
BUDGET_MD = os.path.join(ROOT, "references", "budget.md")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(*args):
    p = subprocess.Popen([sys.executable, SCRIPT] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


class Run(object):
    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="dispatch-")
        return self

    def __exit__(self, *_exc):
        shutil.rmtree(self.d, ignore_errors=True)

    def payload(self, chars, name="p.txt"):
        p = os.path.join(self.d, name)
        io.open(p, "w", encoding="utf-8").write("x" * chars)
        return p

    def cost(self, *triples):
        """(agent, tokens, calls) rows, as cost_log would have written them."""
        with io.open(os.path.join(self.d, "cost.jsonl"), "w", encoding="utf-8") as fh:
            for agent, tokens, calls in triples:
                fh.write(json.dumps({"kind": "agent", "agent": agent, "wave": "1",
                                     "tokens_total": tokens,
                                     "tool_calls": calls}) + "\n")

    def md(self):
        return io.open(os.path.join(self.d, "dispatch.md"), encoding="utf-8").read()

    def jsonl(self):
        p = os.path.join(self.d, "dispatch.jsonl")
        return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


def test_d1_a_payload_is_recorded_by_size():
    with Run() as r:
        rc, out = run("--base", r.d, "--agent", "map-x", "--wave", "1",
                      "--payload-file", r.payload(24000))
        check("D1 recording exits 0", rc == 0, out[:200])
        check("D1 the character count is reported", "24,000 chars" in out, out[:200])
        check("D1 the token figure is offered as derived",
              "[derived]" in out, out[:200])
        rows = r.jsonl()
        check("D1 one row was written", len(rows) == 1, rows)
        check("D1 the row stores characters, not an estimate",
              rows and rows[0]["chars"] == 24000, rows)
        check("D1 and does not store the payload by default",
              rows and "payload" not in rows[0], rows)


def test_d2_the_ledger_is_append_only():
    with Run() as r:
        run("--base", r.d, "--agent", "a", "--wave", "1", "--payload-chars", "100")
        first = io.open(os.path.join(r.d, "dispatch.jsonl"), encoding="utf-8").read()
        run("--base", r.d, "--agent", "b", "--wave", "1", "--payload-chars", "200")
        second = io.open(os.path.join(r.d, "dispatch.jsonl"), encoding="utf-8").read()
        check("D2 the second write appends", second.startswith(first), second[:200])
        check("D2 both rows survive", len(r.jsonl()) == 2, r.jsonl())


def test_d3_the_report_pairs_payload_against_spend():
    with Run() as r:
        r.cost(("arbiter-B", 398092, 43), ("map-x", 237028, 26))
        run("--base", r.d, "--agent", "arbiter-B", "--wave", "1",
            "--payload-file", r.payload(36000, "a.txt"))
        run("--base", r.d, "--agent", "map-x", "--wave", "1",
            "--payload-file", r.payload(24000, "b.txt"))
        md = r.md()
        check("D3 there is a pairing section",
              "## Payload against spend" in md, md[:300])
        check("D3 the product column exists", "payload x calls" in md, md[:600])
        # 36000/4 = 9000 tokens x 43 calls = 387,000 against 398,092 spent
        check("D3 the product is computed", "387,000" in md, md[:900])
        check("D3 and expressed as a share of the spend", "97%" in md, md[:900])
        check("D3 the agent that spent most is listed first",
              md.index("arbiter-B") < md.index("map-x"), md[:900])


def test_d4_a_size_is_measured_and_a_token_is_derived():
    with Run() as r:
        run("--base", r.d, "--agent", "a", "--wave", "1", "--payload-chars", "4000")
        md = r.md()
        rows = [l for l in md.split("\n") if l.startswith("| Payload ")]
        chars = [l for l in rows if "characters" in l]
        toks = [l for l in rows if "tokens" in l]
        check("D4 characters are labelled measured",
              chars and "[measured]" in chars[0], rows)
        check("D4 tokens are labelled derived",
              toks and "[derived]" in toks[0], rows)
        check("D4 the two labels are not interchanged",
              chars and toks and "[derived]" not in chars[0]
              and "[measured]" not in toks[0], rows)
        check("D4 the conversion is stated, not hidden",
              "characters per token" in md, md[:600])


def test_d5_the_script_concludes_nothing():
    body = io.open(SCRIPT, encoding="utf-8").read()
    check("D5 it says it does not optimise",
          "does not optimise anything" in body)
    check("D5 it records why cutting first was wrong before",
          "quadratic" in body and "refused" in body)
    with Run() as r:
        run("--base", r.d, "--agent", "a", "--wave", "1", "--payload-chars", "4000")
        md = r.md()
        check("D5 the page says it concludes nothing",
              "concludes nothing" in md, md[:600])
    check("D5 the cost model withdraws the tool-call cap",
          "withdrawn" in io.open(MODEL, encoding="utf-8").read())
    check("D5 the lever table marks it WITHDRAWN",
          "WITHDRAWN" in io.open(BUDGET_MD, encoding="utf-8").read())


def test_d5_the_measured_refutation_is_written_down():
    model = io.open(MODEL, encoding="utf-8").read()
    for figure in ("0.298", "0.421", "123,460", "222,713", "9.7%"):
        check("D5 %s is recorded in the cost model" % figure, figure in model)
    check("D5 fewer agents is named as the supported lever",
          "fewer agents, not fewer calls" in model)


def test_d6_a_missing_payload_is_refused():
    with Run() as r:
        rc, out = run("--base", r.d, "--agent", "a", "--wave", "1")
        check("D6 no size given is refused", rc == 2, out[:200])
        check("D6 and says what to pass", "--payload-file" in out, out[:200])
        rc, out = run("--base", r.d, "--agent", "a", "--wave", "1",
                      "--payload-file", os.path.join(r.d, "missing.txt"))
        check("D6 a missing payload file is refused", rc == 2, out[:200])
        check("D6 nothing was recorded",
              not os.path.isfile(os.path.join(r.d, "dispatch.jsonl")))


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
