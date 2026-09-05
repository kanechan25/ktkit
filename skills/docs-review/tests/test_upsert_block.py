#!/usr/bin/env python3
"""Two workflows must be able to own two blocks in the same document.

`upsert_block.py` was written for one caller and hardcoded one marker pair. The
chain workflow needs to append its own sync-back block to a `spec.md` that may
already carry a docs-review block. Sharing one marker would mean each run wiped
the other's block and nobody would notice: the file would still look well formed.

So the marker became a parameter, defaulting to the old name. The two things
worth asserting are therefore:

  * the default behaves exactly as before -- no caller had to change;
  * two markers in one file are genuinely independent, in both directions.

The third test guards the delimiter itself. A marker goes inside an HTML
comment, so a name containing `-->` would close the comment early and split the
document in half. That is rejected, not escaped.

Run:  python3 skills/docs-review/tests/test_upsert_block.py
"""
import io
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "upsert_block.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(doc, body, *extra):
    """Invoke the script the way a skill does: through the shell, body on stdin."""
    p = subprocess.Popen([sys.executable, SCRIPT, doc, "--block", "-"] + list(extra),
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate(body.encode("utf-8"), timeout=20)
    return p.returncode, out.decode("utf-8") + err.decode("utf-8")


def write(path, text):
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def test_default_marker_is_unchanged():
    """No existing caller passes --marker, so the default must be the old name."""
    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "doc.md")
        write(doc, "Author text.\n")
        rc, _ = run(doc, "first\n")
        text = read(doc)
        check("default marker still writes docs-review",
              rc == 0 and "<!-- docs-review:begin -->" in text
              and "<!-- docs-review:end -->" in text, text)
        check("author text is copied through byte for byte",
              text.startswith("Author text.\n"), repr(text[:20]))


def test_replacing_is_idempotent_and_does_not_stack():
    """A second run replaces the block; it never appends a second one."""
    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "doc.md")
        write(doc, "Author text.\n")
        run(doc, "first\n")
        run(doc, "second\n")
        text = read(doc)
        check("only one block after two runs",
              text.count("<!-- docs-review:begin -->") == 1, text)
        check("the block holds the newer body",
              "second" in text and "first" not in text, text)


def test_two_markers_are_independent():
    """The point of the change: neither block can destroy the other."""
    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "doc.md")
        write(doc, "Author text.\n")
        run(doc, "review body\n")
        run(doc, "chain body\n", "--marker", "chain")
        text = read(doc)
        check("both blocks exist",
              "<!-- docs-review:begin -->" in text and "<!-- chain:begin -->" in text, text)

        # Updating one must leave the other byte for byte intact, in both
        # directions -- a one-way test would pass on an implementation that
        # always truncates at the first marker it finds.
        run(doc, "review body v2\n")
        text = read(doc)
        check("updating docs-review leaves chain alone",
              "chain body" in text and "review body v2" in text, text)

        run(doc, "chain body v2\n", "--marker", "chain")
        text = read(doc)
        check("updating chain leaves docs-review alone",
              "review body v2" in text and "chain body v2" in text, text)
        check("still exactly one block each",
              text.count("<!-- docs-review:begin -->") == 1
              and text.count("<!-- chain:begin -->") == 1, text)


def test_a_marker_that_would_break_the_comment_is_refused():
    """`-->` inside the name would close the comment and split the document."""
    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "doc.md")
        write(doc, "Author text.\n")
        before = read(doc)
        rc, out = run(doc, "body\n", "--marker", "a-->b")
        check("a marker containing --> exits 2", rc == 2, "rc=%d %s" % (rc, out))
        check("the document was not touched", read(doc) == before, read(doc))

        rc, _ = run(doc, "body\n", "--marker", "")
        check("an empty marker exits 2", rc == 2, "rc=%d" % rc)


def test_an_unclosed_block_is_reported_not_overwritten():
    """A half-written block means an interrupted run. Repairing it silently
    would destroy whatever came after the missing END."""
    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "doc.md")
        write(doc, "Author text.\n\n<!-- chain:begin -->\nhalf\n")
        before = read(doc)
        rc, out = run(doc, "body\n", "--marker", "chain")
        check("an unclosed block exits 1", rc == 1, "rc=%d %s" % (rc, out))
        check("the half-written document was not rewritten", read(doc) == before)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
