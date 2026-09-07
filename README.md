# citeable

**Will ChatGPT, Perplexity or Google AI Overviews *cite* this page? Score it 0-100 and get the exact paragraphs to rewrite.**

[![CI](https://github.com/angelmunizpedraza/citeable/actions/workflows/ci.yml/badge.svg)](https://github.com/angelmunizpedraza/citeable/actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Ranking and being cited are different games. Answer engines lift short, self-contained, verifiable passages from pages that are easy to **chunk**, easy to **attribute** and easy to **trust**. Site-level GEO audits (robots.txt, llms.txt) tell you whether the bots can come in; `citeable` tells you whether a *specific page* gives them anything worth quoting once they are inside.

It is deterministic — no LLM calls, no API keys — so the same page always gets the same score and you can put it in CI or run it before/after a rewrite.

```
$ citeable score https://example.com/boas-surgery https://competitor.com/boas-surgery

# citeable — comparison
| # | Page                                   | Score | Grade | Weakest signal                    |
|---|----------------------------------------|------:|-------|-----------------------------------|
| 1 | BOAS surgery for English bulldogs …    |    92 | A     | Chunk-friendly structure (6.5/10) |
| 2 | Welcome | Best Vet Ever                |    16 | E     | Question-shaped headings (0/10)   |

Gap between best (92) and worst (16): 76 points. Signals where the worst page loses most:
- Structured data: −15 points
- Quotable, specific facts: −15 points
- Question-shaped headings: −10 points

## What to change first (ordered by points at stake)
1. Add concrete, verifiable specifics (numbers, ranges, dates, durations, prices) — aim for one factual sentence per ~70 words…
2. Add structured data: a JSON-LD block, a content type (Article/Service/…), FAQPage for the Q&A sections, author as a Person…
3. Rephrase at least half of the H2s as the literal question a user would type, e.g. "Services" → "What services …?"
4. Only 102 words are visible in the static HTML (AI crawlers do not run JavaScript). Server-render the main content…
```

## The ten signals (100 points)

| Signal | Pts | What it measures | Why engines care |
|---|---:|---|---|
| **Answer-first sections** | 15 | Share of sections whose first paragraph is a 15-70 word direct answer | LLMs lift the first 1-2 sentences under a heading |
| **Quotable, specific facts** | 15 | Sentences with numbers, ranges, dates, units per 100 words; over-long sentences | Specifics get cited; generic advice gets paraphrased without attribution |
| **Structured data** | 15 | JSON-LD, content type, FAQPage/HowTo, author, dates | Disambiguates entity, author and freshness for the retriever |
| **Question-shaped headings** | 10 | H2/H3 phrased as the question a user would type (EN/ES) | Heading ↔ prompt match is the cheapest retrieval win |
| **Authorship & trust** | 10 | Schema author, visible byline, visible date | Attributable, dated content is weighted higher |
| **Readable without JavaScript** | 10 | Words in the static HTML, text/HTML ratio, `<noscript>` warnings | GPTBot, PerplexityBot and ClaudeBot do not execute JS |
| **Chunk-friendly structure** | 10 | Sections in the 60-320 word range; presence of tables/lists | One section = one chunk; tables and steps are quoted almost verbatim |
| **Freshness** | 5 | `dateModified` / visible date age | Time-sensitive prompts prefer dated, recent sources |
| **Cites primary sources** | 5 | Outbound links to .gov/.edu/journals/official bodies | Pages that cite are treated as more citable |
| **Entity clarity** | 5 | Exactly one H1, title/H1 aligned, intro restates the entity | A quoted passage must make sense out of context |

Grades: A ≥ 85 · B ≥ 70 · C ≥ 55 · D ≥ 40 · E below.

Every signal below its threshold produces one recommendation that **quotes the offending heading or paragraph and its word count**, ordered by points at stake — so the report is a to-do list, not a lecture.

## Install

```bash
pip install git+https://github.com/angelmunizpedraza/citeable.git
```

## Usage

```bash
citeable score https://yoursite.com/page                      # one page, Markdown to stdout
citeable score mine.html competitor-1.html competitor-2.html  # local files work too
citeable score URL1 URL2 --md report.md --json data.json --csv scores.csv
citeable score https://yoursite.com/page --min-score 70       # exit 1 below 70 → CI gate
```

Pages are fetched exactly as an AI crawler would (plain GET, no JavaScript). If your score collapses on the live URL but not on the HTML you export from your CMS, the problem is client-side rendering.

### As a CI gate for content

```yaml
- run: pip install git+https://github.com/angelmunizpedraza/citeable.git
- run: citeable score https://staging.example.com/guide --min-score 75
```

### Python API

```python
from citeable import parse_html, score_page
report = score_page(parse_html(html, url))
report.score, report.grade, [s.recommendation for s in report.signals if s.recommendation]
```

## Method notes

* Heuristics, not a model. The thresholds (40-60 word answers, 1.5 factual sentences / 100 words, 60-320 word sections) come from what current engines observably quote; they are constants at the top of `score.py` — tune them for your niche.
* Language-aware where it matters: question detection covers English and Spanish interrogatives; number/date detection is language-neutral.
* It does not measure authority (backlinks, brand mentions) or crawl access. Pair it with [geo-check](https://github.com/angelmunizpedraza/geo-check) (site readiness) and [ai-visibility-tracker](https://github.com/angelmunizpedraza/ai-visibility-tracker) (are you actually cited?).
* Validated on a good/bad fixture pair (92 vs 16) plus 13 unit tests; run it on your own top pages and their competitors — the *relative* gap is the actionable number.

## Project layout

```
citeable/
  extract.py   # HTML → Page (sections, JSON-LD, author, dates, links); nav/footer/scripts stripped
  score.py     # 10 signals → Report with ordered recommendations
  report.py    # Markdown (single + comparison) and CSV
  cli.py       # citeable score
tests/         # 13 tests + good/bad HTML fixtures, no network
```

## Related tools by the same author

The full GEO loop: make the site readable by AI ([geo-check](https://github.com/angelmunizpedraza/geo-check), [llms-txt-generator](https://github.com/angelmunizpedraza/llms-txt-generator)) → make each page **quotable** (citeable) → verify the bots come and the engines cite you ([ai-visibility-tracker](https://github.com/angelmunizpedraza/ai-visibility-tracker), [serp-to-ai-diff](https://github.com/angelmunizpedraza/serp-to-ai-diff)) → tie it to traffic ([ga4-report](https://github.com/angelmunizpedraza/ga4-report)). Technical SEO baseline: [seo-audit](https://github.com/angelmunizpedraza/seo-audit).

## License

MIT © Ángel Muñiz Pedraza — [LinkedIn](https://www.linkedin.com/in/angel-muniz-seo)
