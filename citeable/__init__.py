"""citeable — how likely is this page to be *cited* by AI answer engines?

Ranking in Google and being cited by ChatGPT, Perplexity or Google AI Overviews are
different games. Answer engines pull short, self-contained, verifiable passages from
pages that are easy to chunk, easy to attribute and easy to trust. `citeable` scores a
single URL (or HTML file) on ten signals that predict citability and turns every weak
signal into a concrete rewrite recommendation, quoting the exact heading or paragraph.

It is deliberately deterministic (no LLM calls): the same page always gets the same
score, so you can put it in CI or run it before/after a content change.
"""

__version__ = "0.1.0"

from .extract import Page, parse_html  # noqa: F401
from .score import Report, score_page  # noqa: F401
