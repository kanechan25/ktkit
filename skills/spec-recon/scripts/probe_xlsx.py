#!/usr/bin/env python3
"""Measure an .xlsx workbook with the standard library only.

An .xlsx is a ZIP archive of XML, so it can be measured exactly -- sheet names,
defined names, dimensions, cell text -- without any third-party package.
`openpyxl` is not installed here and must not be assumed anywhere else either.

This file exists so that "never regex a binary file" is executable rather than
advice. Three traps it handles, each of which has produced a confidently wrong
answer when handled by hand:

  * Namespaces. ElementTree reports tags as `{uri}local`. Matching the bare
    local name finds nothing and reads like an empty workbook.
  * Shared strings. Cell text lives in xl/sharedStrings.xml; a cell with t="s"
    holds an index into that table, not a word. Printing the index produces
    plausible nonsense.
  * Inline and rich text. A cell may carry `<is>` inline, and a shared string
    may be split across several `<r>` runs. Reading only the first run silently
    truncates the value.

Usage
    probe_xlsx.py <file.xlsx> [--sheets] [--names] [--dims] [--cells SHEET]
                  [--find TEXT] [--md5] [--json]

    no flag        the summary: md5, size, sheets, defined-name count
    --cells SHEET  every non-empty cell of one sheet as `A1<TAB>value`
    --find TEXT    every cell whose text contains TEXT, across all sheets
    --json         machine-readable, for a script that consumes this

Exit status
    0  measured it
    1  not a readable .xlsx
    2  the arguments are unusable
"""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
Q = "{%s}" % MAIN

CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def shared_strings(z):
    """Return the shared string table, joining every run of each entry."""
    try:
        raw = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    out = []
    for si in root.findall(Q + "si"):
        # A single <t>, or several <r><t> runs that must be concatenated.
        parts = [t.text or "" for t in si.iter(Q + "t")]
        out.append("".join(parts))
    return out


def sheet_index(z):
    """Map sheet name -> the part path that holds it.

    workbook.xml gives names and relationship ids; workbook.xml.rels maps those
    ids to part paths. Assuming sheetN.xml matches the Nth sheet is wrong for
    any workbook whose sheets were reordered or deleted.
    """
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {}
    try:
        rroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for rel in rroot:
            rid = rel.get("Id")
            target = rel.get("Target") or ""
            if target.startswith("/"):
                target = target[1:]
            elif not target.startswith("xl/"):
                target = "xl/" + target
            rels[rid] = target
    except KeyError:
        pass

    out = []
    for sh in wb.iter(Q + "sheet"):
        rid = sh.get("{%s}id" % RELS)
        out.append({"name": sh.get("name"),
                    "sheet_id": sh.get("sheetId"),
                    "state": sh.get("state") or "visible",
                    "part": rels.get(rid)})
    return out


def defined_names(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    return [{"name": dn.get("name"), "refers_to": (dn.text or "").strip()}
            for dn in wb.iter(Q + "definedName")]


def cell_text(c, sst):
    t = c.get("t")
    if t == "s":
        v = c.find(Q + "v")
        if v is None or v.text is None:
            return ""
        try:
            return sst[int(v.text)]
        except (ValueError, IndexError):
            return ""
    if t == "inlineStr":
        is_el = c.find(Q + "is")
        if is_el is None:
            return ""
        return "".join(x.text or "" for x in is_el.iter(Q + "t"))
    v = c.find(Q + "v")
    if v is not None and v.text is not None:
        return v.text
    # A formula cell with no cached value still tells us something.
    f = c.find(Q + "f")
    if f is not None:
        return "=" + (f.text or "")
    return ""


def read_sheet(z, part, sst):
    """Yield (ref, value) for every non-empty cell of one sheet part."""
    if not part:
        return
    try:
        raw = z.read(part)
    except KeyError:
        return
    root = ET.fromstring(raw)
    for row in root.iter(Q + "row"):
        for c in row.findall(Q + "c"):
            val = cell_text(c, sst)
            if val != "":
                yield c.get("r"), val


def dimensions(z, part):
    if not part:
        return None
    try:
        root = ET.fromstring(z.read(part))
    except KeyError:
        return None
    d = root.find(Q + "dimension")
    return d.get("ref") if d is not None else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path")
    ap.add_argument("--sheets", action="store_true")
    ap.add_argument("--names", action="store_true")
    ap.add_argument("--dims", action="store_true")
    ap.add_argument("--cells", metavar="SHEET")
    ap.add_argument("--find", metavar="TEXT")
    ap.add_argument("--md5", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.path):
        sys.stderr.write("no such file: %s\n" % a.path)
        return 2
    try:
        z = zipfile.ZipFile(a.path)
    except (zipfile.BadZipFile, OSError) as exc:
        sys.stderr.write("not a readable .xlsx (%s): %s\n" % (exc, a.path))
        return 1
    try:
        sheets = sheet_index(z)
    except (KeyError, ET.ParseError) as exc:
        sys.stderr.write("no readable workbook part (%s): %s\n" % (exc, a.path))
        return 1

    sst = shared_strings(z)
    result = {
        "path": a.path,
        "md5": md5_of(a.path),
        "bytes": os.path.getsize(a.path),
        "parts": len(z.namelist()),
        "sheets": [s["name"] for s in sheets],
        "sheet_count": len(sheets),
        "hidden_sheets": [s["name"] for s in sheets if s["state"] != "visible"],
        "defined_name_count": len(defined_names(z)),
        "shared_string_count": len(sst),
    }

    if a.dims:
        result["dimensions"] = dict((s["name"], dimensions(z, s["part"]))
                                    for s in sheets)
    if a.names:
        result["defined_names"] = defined_names(z)
    if a.cells:
        match = [s for s in sheets if s["name"] == a.cells]
        if not match:
            sys.stderr.write("no sheet named %r; have: %s\n"
                             % (a.cells, ", ".join(result["sheets"])))
            return 2
        result["cells"] = [{"ref": r, "value": v}
                           for r, v in read_sheet(z, match[0]["part"], sst)]
    if a.find:
        hits = []
        for s in sheets:
            for ref, val in read_sheet(z, s["part"], sst):
                if a.find in val:
                    hits.append({"sheet": s["name"], "ref": ref, "value": val})
        result["find"] = {"needle": a.find, "hits": hits, "count": len(hits)}

    if a.json:
        sys.stdout.write(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
        return 0

    out = sys.stdout
    out.write("path   %s\n" % result["path"])
    out.write("md5    %s\n" % result["md5"])
    out.write("bytes  %d  (%d parts in the archive)\n"
              % (result["bytes"], result["parts"]))
    out.write("sheets %d: %s\n" % (result["sheet_count"],
                                   ", ".join(result["sheets"])))
    if result["hidden_sheets"]:
        out.write("hidden %s\n" % ", ".join(result["hidden_sheets"]))
    out.write("names  %d defined\n" % result["defined_name_count"])
    out.write("strings %d shared\n" % result["shared_string_count"])
    if a.dims:
        for name, ref in result["dimensions"].items():
            out.write("dim    %-24s %s\n" % (name, ref))
    if a.names:
        for dn in result["defined_names"]:
            out.write("name   %-24s %s\n" % (dn["name"], dn["refers_to"]))
    if a.cells:
        for c in result["cells"]:
            out.write("%s\t%s\n" % (c["ref"], c["value"]))
    if a.find:
        for h in result["find"]["hits"]:
            out.write("hit    %s!%s\t%s\n" % (h["sheet"], h["ref"], h["value"]))
        out.write("hits   %d for %r\n" % (result["find"]["count"], a.find))
    return 0


if __name__ == "__main__":
    sys.exit(main())
