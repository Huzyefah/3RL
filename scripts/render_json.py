#!/usr/bin/env python3
"""Render a JSON file to a simple styled HTML page for screenshots.

Usage: render_json.py INPUT.json OUTPUT.html [--title TITLE]
"""

import argparse
import html
import json
import sys
from pathlib import Path

CSS = """
:root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--mut:#666;--bd:#d0d0d0;--k:#0b5cad;--s:#1a7f37;--n:#a15c00}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e8e8e8;--mut:#9a9a9a;--bd:#3a3a3a;--k:#79b8ff;--s:#7ee787;--n:#ffb86c}}
body{background:var(--bg);color:var(--fg);font:14px/1.5 ui-monospace,Menlo,monospace;margin:24px}
h1{font:600 18px system-ui,sans-serif;margin:0 0 16px}
table{border-collapse:collapse;margin:8px 0 16px;width:100%}
th,td{border:1px solid var(--bd);padding:4px 8px;text-align:left;vertical-align:top}
th{font-weight:600}
details{margin-left:16px}summary{cursor:pointer;color:var(--k)}
.k{color:var(--k)}.s{color:var(--s)}.n{color:var(--n)}.m{color:var(--mut)}
"""


def scalar(v):
    if isinstance(v, str):
        return f'<span class="s">{html.escape(v)}</span>'
    return f'<span class="n">{html.escape(json.dumps(v))}</span>'


def is_table(v):
    return (
        isinstance(v, list)
        and v
        and all(isinstance(r, dict) for r in v)
        and all(not isinstance(x, (dict, list)) for r in v for x in r.values())
    )


def render(v):
    if is_table(v):
        cols = list(dict.fromkeys(k for r in v for k in r))
        head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body = "".join(
            "<tr>" + "".join(f"<td>{scalar(r[c]) if c in r else ''}</td>" for c in cols) + "</tr>"
            for r in v
        )
        return f"<table><tr>{head}</tr>{body}</table>"
    if isinstance(v, dict):
        if not v:
            return '<span class="m">{}</span>'
        rows = "".join(
            f'<tr><th class="k">{html.escape(str(k))}</th><td>{render(x)}</td></tr>'
            for k, x in v.items()
        )
        return f"<table>{rows}</table>"
    if isinstance(v, list):
        if not v:
            return '<span class="m">[]</span>'
        return "".join(
            f"<details open><summary>[{i}]</summary>{render(x)}</details>" for i, x in enumerate(v)
        )
    return scalar(v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--title", default=None)
    a = ap.parse_args(argv)
    data = json.loads(Path(a.input).read_text())
    title = a.title or Path(a.input).name
    page = (
        f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body><h1>{html.escape(title)}</h1>{render(data)}</body></html>"
    )
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(page)
    print(f"wrote {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
