"""Ten deterministic citability signals, 100 points, every weak signal becomes a recommendation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

from .extract import DATE_RE, NUMBER_RE, QUESTION_WORDS, WORD_RE, Page, Section


@dataclass
class Signal:
    key: str
    label: str
    points: float
    max_points: int
    evidence: str
    recommendation: Optional[str] = None   # None when the signal is healthy

    @property
    def pct(self) -> float:
        return self.points / self.max_points if self.max_points else 0.0


@dataclass
class Report:
    url: str
    title: str
    score: int
    grade: str
    signals: List[Signal]
    words: int
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url": self.url, "title": self.title, "score": self.score, "grade": self.grade, "words": self.words,
            "signals": [{"key": s.key, "label": s.label, "points": round(s.points, 1), "max": s.max_points, "evidence": s.evidence, "recommendation": s.recommendation} for s in self.signals],
            "recommendations": self.recommendations,
        }


def _wc(text: str) -> int:
    return len(WORD_RE.findall(text))


def _short(s: str, n: int = 70) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _is_question(h: str) -> bool:
    h = h.strip()
    return h.endswith("?") or bool(QUESTION_WORDS.match(h))


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m"):
        try:
            return datetime.strptime(s[: len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    m = DATE_RE.search(s)
    if m and m.group(1):
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(4) or 1))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------- signals

def sig_answer_first(page: Page) -> Signal:
    """Does each section open with a short, direct answer? (LLMs lift the first 1-2 sentences under a heading.)"""
    secs = [s for s in page.sections if s.paragraphs]
    if not secs:
        return Signal("answer_first", "Answer-first sections", 0, 15, "No paragraphs found in main content", "Add real paragraphs (<p>) under each heading; content inside divs/spans only is often skipped.")
    good = [s for s in secs if 15 <= s.first_paragraph_words <= 70]
    ratio = len(good) / len(secs)
    long_ = [s for s in secs if s.first_paragraph_words > 70][:3]
    short = [s for s in secs if s.first_paragraph_words < 15][:3]
    pts = round(15 * ratio, 1)
    ev = f"{len(good)}/{len(secs)} sections open with a 15-70 word direct answer"
    rec = None
    if ratio < 0.7:
        parts = []
        if long_:
            parts.append("too long: " + "; ".join(f'"{_short(s.heading)}" ({s.first_paragraph_words} words)' for s in long_))
        if short:
            parts.append("too thin: " + "; ".join(f'"{_short(s.heading)}" ({s.first_paragraph_words} words)' for s in short))
        rec = "Open each section with one self-contained 40-60 word answer before the detail. Openers " + " · ".join(parts) + "."
    return Signal("answer_first", "Answer-first sections", pts, 15, ev, rec)


def sig_question_headings(page: Page) -> Signal:
    """Headings phrased as the questions people ask an assistant map directly onto prompts."""
    heads = [s.heading for s in page.sections[1:] if s.heading]
    if not heads:
        return Signal("question_headings", "Question-shaped headings", 0, 10, "No H2/H3 headings", "Break the page into H2/H3 sections; a single wall of text cannot be chunked or attributed.")
    q = [h for h in heads if _is_question(h)]
    ratio = len(q) / len(heads)
    pts = round(10 * min(1.0, ratio / 0.5), 1)   # 50% question-shaped = full marks
    rec = None
    if ratio < 0.3:
        ex = heads[0]
        rec = f'Rephrase at least half of the H2s as the literal question a user would type, e.g. "{_short(ex, 40)}" → "How/What/Why … {_short(ex, 30).lower()}?"'
    return Signal("question_headings", "Question-shaped headings", pts, 10, f"{len(q)}/{len(heads)} headings are question-shaped", rec)


def sig_quotable_facts(page: Page) -> Signal:
    """Sentences with numbers, dates, units or ranges are what engines quote and attribute."""
    sents = page.sentences()
    if not sents:
        return Signal("quotable_facts", "Quotable, specific facts", 0, 15, "No sentences found", "Write in complete sentences; engines quote sentences, not fragments.")
    factual = [s for s in sents if NUMBER_RE.search(s) or DATE_RE.search(s)]
    per100 = len(factual) / max(1, page.text_words) * 100
    # 1.5 factual sentences per 100 words = full marks
    pts = round(15 * min(1.0, per100 / 1.5), 1)
    long_sents = sum(1 for s in sents if _wc(s) > 35)
    rec = None
    if per100 < 1.0:
        rec = "Add concrete, verifiable specifics (numbers, ranges, dates, durations, prices, sample sizes) — aim for one factual sentence per ~70 words. Generic advice is paraphrased without attribution; specifics get cited."
    elif long_sents / len(sents) > 0.3:
        rec = f"{long_sents} sentences exceed 35 words; split them — a citation is usually a single sentence."
    return Signal("quotable_facts", "Quotable, specific facts", pts, 15, f"{len(factual)} factual sentences in {page.text_words} words ({per100:.1f}/100 words)", rec)


def sig_structured_data(page: Page) -> Signal:
    types = set(page.schema_types)
    content_types = {"Article", "NewsArticle", "BlogPosting", "TechArticle", "MedicalWebPage", "FAQPage", "HowTo", "Product", "Service", "LocalBusiness", "Organization", "Person", "WebPage", "Recipe", "Course", "Event", "Dataset", "ScholarlyArticle", "QAPage"}
    pts = 0.0
    parts = []
    if page.jsonld:
        pts += 4; parts.append("JSON-LD present")
    hits = types & content_types
    if hits:
        pts += 4; parts.append("types: " + ", ".join(sorted(hits)[:5]))
    if "FAQPage" in types or "HowTo" in types or "QAPage" in types:
        pts += 3; parts.append("Q&A/HowTo markup")
    if page.author:
        pts += 2; parts.append("author in schema")
    if page.date_modified or page.date_published:
        pts += 2; parts.append("dates in schema")
    rec = None
    if pts < 10:
        missing = []
        if not page.jsonld: missing.append("a JSON-LD block")
        if not hits: missing.append("a content type (Article/Service/Product/MedicalWebPage…)")
        if not ({"FAQPage", "HowTo", "QAPage"} & types): missing.append("FAQPage for the Q&A sections")
        if not page.author: missing.append("author as a Person with sameAs")
        if not (page.date_modified or page.date_published): missing.append("datePublished/dateModified")
        rec = "Add structured data: " + ", ".join(missing) + "."
    return Signal("structured_data", "Structured data", min(15, pts), 15, "; ".join(parts) or "none", rec)


def sig_authorship(page: Page) -> Signal:
    pts = 0.0
    parts = []
    if page.author:
        pts += 4; parts.append(f"author: {page.author}")
    if page.byline_text:
        pts += 3; parts.append("visible byline")
    if page.visible_dates:
        pts += 3; parts.append("visible date")
    rec = None
    if pts < 7:
        rec = "Show who wrote/reviewed the page (visible byline + Person schema with credentials and sameAs to LinkedIn/press) and a visible 'last updated' date. Engines weight attributable, dated content."
    return Signal("authorship", "Authorship & trust signals", pts, 10, "; ".join(parts) or "no author, byline or visible date", rec)


def sig_freshness(page: Page, today: Optional[date] = None) -> Signal:
    today = today or date.today()
    d = _parse_date(page.date_modified) or _parse_date(page.date_published) or next((x for x in map(_parse_date, page.visible_dates) if x), None)
    if not d:
        return Signal("freshness", "Freshness", 0, 5, "no machine-readable date", "Add dateModified (schema) and a visible 'Updated on' line; undated pages lose to dated ones on time-sensitive prompts.")
    months = (today.year - d.year) * 12 + today.month - d.month
    pts = 5 if months <= 6 else 3 if months <= 12 else 1 if months <= 24 else 0
    rec = None if pts >= 3 else f"Content last dated {d.isoformat()} ({months} months ago). Review, update facts and bump dateModified."
    return Signal("freshness", "Freshness", pts, 5, f"last dated {d.isoformat()} ({months} months ago)", rec)


def sig_readability_nojs(page: Page) -> Signal:
    words = page.text_words
    ratio = (len(page.body_text.encode("utf-8", "ignore")) / page.html_bytes) if page.html_bytes else 0
    pts = 0.0
    if words >= 300: pts += 6
    elif words >= 120: pts += 3
    if ratio >= 0.10: pts += 4
    elif ratio >= 0.04: pts += 2
    rec = None
    if words < 300:
        rec = f"Only {words} words are visible in the static HTML (AI crawlers do not run JavaScript). Server-render the main content or add static HTML fallbacks."
    elif ratio < 0.04:
        rec = f"Text is {ratio:.1%} of the HTML payload; heavy markup/scripts dilute the extractable content. Trim inline scripts/SVG and move boilerplate out of the main container."
    if page.noscript_warning:
        rec = (rec or "") + " A <noscript> 'enable JavaScript' notice suggests the real content is client-rendered."
    return Signal("readability_nojs", "Readable without JavaScript", pts, 10, f"{words} words in static HTML; text/HTML ratio {ratio:.1%}", rec.strip() if rec else None)


def sig_chunkability(page: Page) -> Signal:
    secs = [s for s in page.sections if s.words > 0]
    if not secs:
        return Signal("chunkability", "Chunk-friendly structure", 0, 10, "no content sections", "Structure the content in H2/H3 sections of 80-300 words.")
    ideal = [s for s in secs if 60 <= s.words <= 320]
    ratio = len(ideal) / len(secs)
    pts = round(7 * ratio, 1)
    if page.lists or page.tables:
        pts += 3
    huge = sorted((s for s in secs if s.words > 320), key=lambda s: -s.words)[:2]
    rec = None
    if ratio < 0.6 or huge:
        h = "; ".join(f'"{_short(s.heading)}" ({s.words} words)' for s in huge)
        rec = f"Keep sections between 80 and 300 words so each can be lifted as one chunk. Split: {h}." if h else "Merge very short sections (<60 words) or expand them into complete answers."
    if not (page.lists or page.tables):
        rec = (rec + " " if rec else "") + "Add at least one table or list: engines extract comparisons and steps from them almost verbatim."
    return Signal("chunkability", "Chunk-friendly structure", min(10, pts), 10, f"{len(ideal)}/{len(secs)} sections in the 60-320 word range; {page.tables} tables, {page.lists} lists", rec)


def sig_sources(page: Page) -> Signal:
    n_auth = len(set(page.authority_links))
    n_out = len(set(page.outbound_links))
    pts = min(5, n_auth * 2 + (1 if n_out else 0))
    rec = None
    if n_auth == 0:
        rec = "Cite 2-3 primary sources (studies, official bodies, standards) with outbound links. Pages that cite are treated as more citable."
    return Signal("sources", "Cites primary sources", pts, 5, f"{n_auth} authoritative outbound links of {n_out} total", rec)


def sig_entity_clarity(page: Page) -> Signal:
    pts = 0.0
    parts = []
    if len(page.h1) == 1:
        pts += 2; parts.append("exactly one H1")
    elif not page.h1:
        parts.append("no H1")
    else:
        parts.append(f"{len(page.h1)} H1s")
    if page.title and page.h1 and (set(WORD_RE.findall(page.title.lower())) & set(WORD_RE.findall(page.h1[0].lower()))):
        pts += 1; parts.append("title/H1 aligned")
    intro = page.sections[0].text if page.sections else ""
    if page.h1 and intro:
        h1_words = {w for w in WORD_RE.findall(page.h1[0].lower()) if len(w) > 3}
        if h1_words and len(h1_words & set(WORD_RE.findall(intro.lower()))) >= max(1, len(h1_words) // 2):
            pts += 2; parts.append("intro restates the topic entity")
    rec = None
    if pts < 4:
        rec = "Use exactly one H1 that names the entity/topic, and restate it in the first sentence ('X is …') so the passage is self-contained when quoted out of context."
    return Signal("entity_clarity", "Entity clarity", pts, 5, "; ".join(parts), rec)


SIGNALS = [sig_answer_first, sig_question_headings, sig_quotable_facts, sig_structured_data, sig_authorship, sig_freshness, sig_readability_nojs, sig_chunkability, sig_sources, sig_entity_clarity]


def grade(score: int) -> str:
    return "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "E"


def score_page(page: Page, today: Optional[date] = None) -> Report:
    signals = []
    for fn in SIGNALS:
        signals.append(fn(page, today) if fn is sig_freshness else fn(page))
    total = int(round(sum(s.points for s in signals)))
    # recommendations ordered by points lost
    recs = [s.recommendation for s in sorted(signals, key=lambda s: -(s.max_points - s.points)) if s.recommendation]
    return Report(url=page.url, title=page.title or (page.h1[0] if page.h1 else page.url), score=total, grade=grade(total), signals=signals, words=page.text_words, recommendations=recs)
