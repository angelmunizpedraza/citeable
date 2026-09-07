"""Turn raw HTML into a structured `Page` the scorer can reason about.

Only the *static* HTML is analysed on purpose: most AI crawlers (GPTBot, PerplexityBot,
ClaudeBot) do not execute JavaScript, so what you see here is what they see.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

NOISE_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "iframe", "template"}
WORD_RE = re.compile(r"[\wÀ-ÿ'’-]+", re.UNICODE)
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ0-9¿¡\"“(])")
QUESTION_WORDS = re.compile(
    r"^(how|what|why|when|where|which|who|can|does|do|is|are|should|c[oó]mo|qu[eé]|por qu[eé]|cu[aá]ndo|d[oó]nde|cu[aá]l|cu[aá]nto|qui[eé]n|es|son|puedo|se puede)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![\w/])(\$|€|£)?\d[\d.,]*\s?(%|€|\$|£|km|kg|g|mg|ml|h|min|hours?|days?|weeks?|months?|years?|d[ií]as?|semanas?|meses|años?|horas?|minutos?|mm|cm|m|k|M|x)?(?![\w/])")
DATE_RE = re.compile(r"\b(20\d{2}|19\d{2})[-/.](0?[1-9]|1[0-2])([-/.](0?[1-9]|[12]\d|3[01]))?\b|\b(0?[1-9]|[12]\d|3[01])[/.](0?[1-9]|1[0-2])[/.](20\d{2})\b")
AUTHORITY_TLDS = (".gov", ".edu", ".ac.uk", ".gob.es", ".europa.eu", ".who.int", ".nih.gov")
AUTHORITY_DOMAINS = ("wikipedia.org", "nature.com", "sciencedirect.com", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "bmj.com", "thelancet.com", "avma.org", "rcvs.org.uk", "ine.es", "boe.es", "w3.org", "developers.google.com", "developer.mozilla.org")


@dataclass
class Section:
    level: int            # 1..6
    heading: str
    paragraphs: List[str] = field(default_factory=list)
    has_list: bool = False
    has_table: bool = False

    @property
    def text(self) -> str:
        return " ".join(self.paragraphs)

    @property
    def words(self) -> int:
        return len(WORD_RE.findall(self.text))

    @property
    def first_paragraph_words(self) -> int:
        return len(WORD_RE.findall(self.paragraphs[0])) if self.paragraphs else 0


@dataclass
class Page:
    url: str
    title: str = ""
    h1: List[str] = field(default_factory=list)
    lang: str = ""
    sections: List[Section] = field(default_factory=list)   # sections[0] is the intro (before first h2)
    jsonld: List[dict] = field(default_factory=list)
    schema_types: List[str] = field(default_factory=list)
    author: Optional[str] = None
    date_published: Optional[str] = None
    date_modified: Optional[str] = None
    visible_dates: List[str] = field(default_factory=list)
    byline_text: Optional[str] = None
    outbound_links: List[str] = field(default_factory=list)
    authority_links: List[str] = field(default_factory=list)
    internal_links: int = 0
    html_bytes: int = 0
    text_words: int = 0
    noscript_warning: bool = False
    tables: int = 0
    lists: int = 0
    images_without_alt: int = 0
    images: int = 0

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc.lower().removeprefix("www.")

    @property
    def body_text(self) -> str:
        return " ".join(s.text for s in self.sections)

    def sentences(self) -> List[str]:
        out: List[str] = []
        for s in self.sections:
            for p in s.paragraphs:
                out.extend(x.strip() for x in SENT_SPLIT_RE.split(p) if x.strip())
        return out


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _walk_jsonld(node, types: List[str], found: Dict[str, Optional[str]]):
    if isinstance(node, list):
        for n in node:
            _walk_jsonld(n, types, found)
        return
    if not isinstance(node, dict):
        return
    t = node.get("@type")
    if isinstance(t, list):
        types.extend(str(x) for x in t)
    elif t:
        types.append(str(t))
    for key, target in (("datePublished", "published"), ("dateModified", "modified")):
        if node.get(key) and not found.get(target):
            found[target] = str(node[key])[:10]
    a = node.get("author")
    if a and not found.get("author"):
        if isinstance(a, list):
            a = a[0] if a else None
        if isinstance(a, dict):
            found["author"] = a.get("name") or None
            if a.get("@type") == "Organization":
                found["author_is_org"] = "1"
        elif isinstance(a, str):
            found["author"] = a
    for v in node.values():
        if isinstance(v, (dict, list)):
            _walk_jsonld(v, types, found)


def parse_html(html: str, url: str = "file://local") -> Page:
    soup = BeautifulSoup(html, "html.parser")
    page = Page(url=url, html_bytes=len(html.encode("utf-8", "ignore")))
    page.lang = (soup.html.get("lang") or "") if soup.html else ""
    page.title = _clean(soup.title.get_text()) if soup.title else ""
    page.noscript_warning = bool(soup.find("noscript") and re.search(r"enable|activ", soup.find("noscript").get_text(), re.I))

    # JSON-LD
    for tag in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except Exception:
            continue
        page.jsonld.append(data if isinstance(data, dict) else {"@graph": data})
    found: Dict[str, Optional[str]] = {}
    for d in page.jsonld:
        _walk_jsonld(d, page.schema_types, found)
    page.author = found.get("author")
    page.date_published = found.get("published")
    page.date_modified = found.get("modified")

    # meta fallbacks
    for name in ("article:modified_time", "article:published_time", "date", "last-modified"):
        m = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if m and m.get("content"):
            if "modified" in name and not page.date_modified:
                page.date_modified = m["content"][:10]
            elif not page.date_published:
                page.date_published = m["content"][:10]
    if not page.author:
        m = soup.find("meta", attrs={"name": "author"})
        if m and m.get("content"):
            page.author = _clean(m["content"])

    # byline heuristics (visible)
    byline = soup.find(attrs={"rel": "author"}) or soup.find(class_=re.compile("byline|author", re.I))
    if byline:
        page.byline_text = _clean(byline.get_text())[:120] or None
    for t in soup.find_all("time"):
        v = t.get("datetime") or t.get_text()
        if v:
            page.visible_dates.append(_clean(v)[:10])

    # links
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        h = urlparse(href).netloc.lower().removeprefix("www.")
        if not h or h == host:
            page.internal_links += 1
            continue
        page.outbound_links.append(href)
        if h.endswith(AUTHORITY_TLDS) or any(h == d or h.endswith("." + d) for d in AUTHORITY_DOMAINS):
            page.authority_links.append(href)

    # images
    for img in soup.find_all("img"):
        page.images += 1
        if not _clean(img.get("alt") or ""):
            page.images_without_alt += 1

    # main content: prefer <main>/<article>, else body
    root = soup.find("main") or soup.find("article") or soup.body or soup
    for t in root.find_all(NOISE_TAGS):
        t.decompose()

    page.h1 = [_clean(h.get_text()) for h in root.find_all("h1")]
    intro = Section(level=1, heading=page.h1[0] if page.h1 else page.title)
    page.sections.append(intro)
    current = intro
    for el in root.descendants:
        if not isinstance(el, Tag):
            continue
        name = el.name
        if name in ("h2", "h3", "h4"):
            current = Section(level=int(name[1]), heading=_clean(el.get_text()))
            page.sections.append(current)
        elif name == "p":
            txt = _clean(el.get_text())
            if len(WORD_RE.findall(txt)) >= 4:
                current.paragraphs.append(txt)
        elif name in ("ul", "ol"):
            if el.find_parent(["nav", "ul", "ol"]) is None:
                current.has_list = True
                page.lists += 1
                items = [_clean(li.get_text()) for li in el.find_all("li", recursive=False)]
                if items:
                    current.paragraphs.append(" ".join(items))
        elif name == "table":
            current.has_table = True
            page.tables += 1
    page.text_words = len(WORD_RE.findall(page.body_text))
    return page


def fetch(url: str, timeout: int = 20) -> str:
    """Fetch a page the way an AI crawler would: plain GET, no JS, honest UA."""
    import requests

    r = requests.get(url, timeout=timeout, headers={"User-Agent": "citeable/0.1 (+https://github.com/angelmunizpedraza/citeable)"})
    r.raise_for_status()
    return r.text
