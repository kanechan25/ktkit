#!/usr/bin/env python3
"""The pin is the only feature pointer that survives between tool calls.

Every property tested here corresponds to a way a speckit-backed phase would
write into the wrong feature, or refuse to run at all:

  * a pin left behind by an earlier feature and never replaced => the next
    `setup-plan.sh` resolves it, copies the plan template over that feature's
    `plan.md`, and reports success -- the failure mode that motivated this
    script, and the reason writing the pin is a step rather than a detail;
  * a pin written as an absolute path, or with the caller's own normalisation
    => a later reader compares strings and decides the pin is wrong;
  * a pin that replaces the whole file => any sibling key spec-kit or a user
    put there is gone, silently;
  * a pin accepted for a directory nobody created => the pin resolves and the
    branch-name gate fires anyway, because the bypass tests the path with `-d`;
  * a hard failure in a repository with no `.specify/` => one call site can no
    longer serve both the speckit path and the internalised one.

Run:  python3 skills/chain/tests/test_speckit_pin.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PIN = os.path.join(ROOT, "scripts", "speckit_pin.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(*args):
    p = subprocess.Popen([sys.executable, PIN] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(timeout=20)
    return p.returncode, (out + err).decode("utf-8").strip()


def repo(tmp, pinned=None, extra=None, scaffold=True):
    """A repository with two feature directories, optionally already pinned."""
    if scaffold:
        os.makedirs(os.path.join(tmp, ".specify"))
    for name in ("inventory-sync", "order-export"):
        os.makedirs(os.path.join(tmp, "specs", name))
    if pinned is not None and scaffold:
        doc = {"feature_directory": pinned}
        if extra:
            doc.update(extra)
        with open(os.path.join(tmp, ".specify", "feature.json"), "w") as fh:
            fh.write(json.dumps(doc, indent=2) + "\n")
    return tmp


def pinned_value(tmp):
    path = os.path.join(tmp, ".specify", "feature.json")
    with open(path, "r") as fh:
        return json.load(fh)


def test_a_stale_pin_is_replaced_and_the_old_value_reported():
    """The motivating case: a pointer left behind by an unrelated feature."""
    with tempfile.TemporaryDirectory() as d:
        repo(d, pinned="specs/inventory-sync")
        rc, out = run("--dir", "specs/order-export", "--repo", d)
        check("stale pin exits 0", rc == 0, out)
        check("new value written",
              pinned_value(d)["feature_directory"] == "specs/order-export", out)
        check("old value named in the report", "specs/inventory-sync" in out, out)


def test_b_pin_is_repository_relative_with_forward_slashes():
    """Written the way spec-kit's own writer writes it, so the checkout can
    move and a later reader's string comparison still agrees."""
    with tempfile.TemporaryDirectory() as d:
        repo(d)
        rc, out = run("--dir", os.path.join(d, "specs", "order-export"),
                      "--repo", d)
        value = pinned_value(d)["feature_directory"]
        check("absolute --dir is stored relative",
              rc == 0 and value == "specs/order-export", "%s %s" % (value, out))


def test_c_sibling_keys_survive():
    """This script owns one key, not the file."""
    with tempfile.TemporaryDirectory() as d:
        repo(d, pinned="specs/inventory-sync",
             extra={"custom_setting": "keep me"})
        run("--dir", "specs/order-export", "--repo", d)
        doc = pinned_value(d)
        check("sibling key kept", doc.get("custom_setting") == "keep me",
              json.dumps(doc))


def test_d_repinning_the_same_directory_is_idempotent():
    """Called once per phase, so an unchanged pin must not churn the file."""
    with tempfile.TemporaryDirectory() as d:
        repo(d, pinned="specs/order-export")
        rc, out = run("--dir", "./specs/order-export", "--repo", d)
        check("differently normalised same target is unchanged",
              rc == 0 and "unchanged" in out, out)


def test_e_a_directory_that_does_not_exist_is_refused():
    """The branch-gate bypass tests the pinned path with `-d`. Pinning a path
    nobody created buys a pin that resolves and a gate that still fires."""
    with tempfile.TemporaryDirectory() as d:
        repo(d)
        rc, out = run("--dir", "specs/not-created-yet", "--repo", d)
        check("missing directory exits 2", rc == 2, out)
        check("nothing written",
              not os.path.isfile(os.path.join(d, ".specify", "feature.json")),
              out)


def test_f_verify_separates_a_wrong_pin_from_a_right_one():
    """The gate a phase runs before trusting a speckit call it did not make."""
    with tempfile.TemporaryDirectory() as d:
        repo(d, pinned="specs/inventory-sync")
        rc_bad, out_bad = run("--dir", "specs/order-export", "--verify",
                              "--repo", d)
        check("wrong pin exits 1", rc_bad == 1, out_bad)
        check("verify wrote nothing",
              pinned_value(d)["feature_directory"] == "specs/inventory-sync",
              out_bad)
        rc_ok, out_ok = run("--dir", "specs/inventory-sync", "--verify",
                            "--repo", d)
        check("right pin exits 0", rc_ok == 0, out_ok)


def test_g_no_scaffolding_skips_instead_of_failing():
    """One call site has to serve the internalised path too."""
    with tempfile.TemporaryDirectory() as d:
        repo(d, scaffold=False)
        rc, out = run("--dir", "specs/order-export", "--repo", d)
        check("no .specify/ exits 0", rc == 0, out)
        check("reported as SKIP", out.startswith("SKIP"), out)


def test_h_unparseable_pin_is_backed_up_not_merged():
    """Dropping keys nobody could read is how a config file loses data."""
    with tempfile.TemporaryDirectory() as d:
        repo(d)
        path = os.path.join(d, ".specify", "feature.json")
        with open(path, "w") as fh:
            fh.write("{ this is not json\n")
        rc, out = run("--dir", "specs/order-export", "--repo", d)
        check("unparseable file still pins", rc == 0, out)
        check("new value written",
              pinned_value(d)["feature_directory"] == "specs/order-export", out)
        check("previous bytes backed up",
              os.path.isfile(path + ".bak"), out)


def test_i_print_reports_an_unset_pin_without_writing():
    """Used at preflight time, before any feature directory is resolved."""
    with tempfile.TemporaryDirectory() as d:
        repo(d)
        rc, out = run("--print", "--repo", d)
        check("--print exits 0", rc == 0, out)
        check("unset pin named as such", "unset" in out, out)
        check("--print wrote nothing",
              not os.path.isfile(os.path.join(d, ".specify", "feature.json")),
              out)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
