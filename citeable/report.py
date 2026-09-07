"""Markdown / CSV rendering for one or many reports."""

from __future__ import annotations

import csv
import io
from typing import List

from .score import Report


def _bar(pct: float, width: int = 10) -> str:
    n = int(round(pct * width))
    return "█" * n + "░" * (width - n)


def markdown_one(r: Report) -> str:
    L = [f"# citeable — {r.title}", "", f"`{r.url}`", "", f"**Score: {r.score}/100 · Grade {r.grade}** · {r.words} words in static HTML", ""]
    L += ["| Signal | Points | | Evidence |", "|---|---:|---|---|"]
    for s in r.signals:
        L.append(f"| {s.label} | {s.points:g}/{s.max_points} | `{_bar(s.pct)}` | {s.evidence} |")
    L.append("")
    if r.recommendations:
        L.append("## What to change first (ordered by points at stake)")
        L.append("")
        for i, rec in enumerate(r.recommendations, 1):
            L.append(f"{i}. {rec}")
        L.append("")
    else:
        L.append("No recommendations — this page is in good shape for AI citation.")
        L.append("")
    return "\n".join(L)


def markdown_many(reports: List[Report]) -> str:
    if len(reports) == 1:
        return markdown_one(reports[0])
    rs = sorted(reports, key=lambda r: -r.score)
    L = ["# citeable — comparison", "", "| # | Page | Score | Grade | Weakest signal |", "|---:|---|---:|---|---|"]
    for i, r in enumerate(rs, 1):
        weakest = min(r.signals, key=lambda s: s.pct)
        L.append(f"| {i} | [{r.title[:60]}]({r.url}) | {r.score} | {r.grade} | {weakest.label} ({weakest.points:g}/{weakest.max_points}) |")
    L.append("")
    if len(rs) >= 2:
        top, mine = rs[0], rs[-1]
        L.append(f"Gap between best ({top.score}) and worst ({mine.score}): **{top.score - mine.score} points**. Signals where the worst page loses most vs the best:")
        L.append("")
        diffs = sorted(((t.points - m.points, t.label) for t, m in zip(top.signals, mine.signals)), reverse=True)
        for d, label in diffs[:3]:
            if d > 0:
                L.append(f"- {label}: −{d:g} points")
        L.append("")
    L.append("---")
    L.append("")
    for r in rs:
        L.append(markdown_one(r))
        L.append("")
    return "\n".join(L)


def csv_text(reports: List[Report]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    keys = [s.key for s in reports[0].signals] if reports else []
    w.writerow(["url", "title", "score", "grade", "words", *keys])
    for r in reports:
        w.writerow([r.url, r.title, r.score, r.grade, r.words, *[round(s.points, 1) for s in r.signals]])
    return buf.getvalue()
