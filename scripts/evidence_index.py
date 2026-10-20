#!/usr/bin/env python3
"""Check phase evidence and write the flow table into REPORT.md.

Usage: evidence_index.py phase-NN-slug [--root DIR]
Reads scripts/phases.json (stdlib only). Exit 1 if a required flow has no PNG.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
START, END = "<!-- evidence:start -->", "<!-- evidence:end -->"

TEMPLATE = """# Phase {nn} ({slug}): gate record
Commit: <sha> · Date: {date} · Branch: phase/{nn}-{slug} · Tag: phase-{nn} · PR: <url>

## Commands run (verbatim) and results
| Command | pass / fail / skip |
|---|---|

## Evidence flows
{start}
{end}

## Exit criteria
- [ ] (copy from the plan)

## Interface changes since last freeze

## Skipped / deferred (with reason)

## Review findings and resolutions
"""


def load_phases():
    return json.loads((HERE / "phases.json").read_text())


def resolve(arg, phases):
    m = re.fullmatch(r"phase-(\w+?)-(.+)", arg)
    if not m:
        sys.exit(f"bad phase id {arg!r}; expected phase-NN-slug")
    nn, slug = m.groups()
    entry = phases.get(nn)
    if entry is None or entry["slug"] != slug:
        sys.exit(
            f"{arg}: not in phases.json (known: "
            + ", ".join(f"phase-{k}-{v['slug']}" for k, v in phases.items())
            + ")"
        )
    return nn, slug, entry


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("phase", help="phase-NN-slug, e.g. phase-00-foundation")
    ap.add_argument("--root", default=str(HERE.parent / "test-evidence"), help="evidence root")
    args = ap.parse_args(argv)

    phases = load_phases()
    nn, slug, entry = resolve(args.phase, phases)
    pdir = Path(args.root) / args.phase
    optional = set(entry.get("optional_flows", []))
    rows, missing = [], []
    # Keep hand-written "What it proves" text from a previous run.
    kept = {}
    prev = pdir / "REPORT.md"
    if prev.exists():
        for line in prev.read_text().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 3 and cells[2] not in ("", "<fill in>", "What it proves", "---", "skipped"):
                kept[cells[0]] = cells[2]
    for flow in entry["evidence_flows"]:
        pngs = sorted((pdir / flow).glob("*.png")) if (pdir / flow).is_dir() else []
        if pngs:
            names = ", ".join(p.name for p in pngs)
            rows.append(f"| {flow} | {len(pngs)}: {names} | {kept.get(flow, "<fill in>")} |")
        elif flow in optional:
            rows.append(f"| {flow} | none (optional, skipped) | skipped |")
        else:
            rows.append(f"| {flow} | MISSING | |")
            missing.append(flow)
    table = "\n".join(["| Flow | Screenshots | What it proves |", "|---|---|---|", *rows])

    pdir.mkdir(parents=True, exist_ok=True)
    report = pdir / "REPORT.md"
    if not report.exists():
        report.write_text(
            TEMPLATE.format(
                nn=nn, slug=slug, date=datetime.date.today().isoformat(), start=START, end=END
            )
        )
    text = report.read_text()
    block = f"{START}\n{table}\n{END}"
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    else:
        text += f"\n## Evidence flows\n{block}\n"
    report.write_text(text)

    print(table)
    if missing:
        print(f"\nFAIL: no PNG for flow(s): {', '.join(missing)}", file=sys.stderr)
        return 1
    print(f"\nOK: {len(entry['evidence_flows'])} flows have evidence; wrote {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
