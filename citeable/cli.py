"""citeable CLI.

    citeable score https://example.com/page [more urls or .html files] [--md out.md] [--json out.json] [--csv out.csv]
    citeable score mine.html competitor.html            # compare
    citeable score URL --min-score 70                   # exit 1 if below (for CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from . import __version__
from .extract import fetch, parse_html
from .report import csv_text, markdown_many
from .score import score_page


def load(target: str) -> tuple[str, str]:
    """Return (url, html) for a URL or a local HTML file."""
    p = Path(target)
    if p.exists():
        return f"file://{p.resolve()}", p.read_text(encoding="utf-8", errors="ignore")
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    return target, fetch(target)


def _cmd_score(a: argparse.Namespace) -> int:
    reports = []
    for t in a.targets:
        try:
            url, html = load(t)
        except Exception as e:  # network or file error: report and continue
            print(f"[warn] {t}: {e}", file=sys.stderr)
            continue
        rep = score_page(parse_html(html, url))
        reports.append(rep)
        if a.verbose:
            print(f"[{rep.score:3d} {rep.grade}] {url}", file=sys.stderr)
    if not reports:
        print("error: nothing scored", file=sys.stderr)
        return 2
    md = markdown_many(reports)
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False), encoding="utf-8")
    if a.csv:
        Path(a.csv).write_text(csv_text(reports), encoding="utf-8")
    if not (a.md or a.json or a.csv):
        print(md)
    if a.min_score is not None and min(r.score for r in reports) < a.min_score:
        print(f"citeable: score below --min-score {a.min_score}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="citeable", description="Score how citable a page is for AI answer engines.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="Score one or more URLs / HTML files (several = comparison table)")
    s.add_argument("targets", nargs="+", help="URLs or local .html files")
    s.add_argument("--md")
    s.add_argument("--json")
    s.add_argument("--csv")
    s.add_argument("--min-score", type=int, help="Exit 1 if any page scores below this (CI gate)")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=_cmd_score)
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
