from datetime import date
from pathlib import Path

from citeable import parse_html, score_page
from citeable.score import _is_question, _parse_date, grade

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 7)


def load(name):
    return parse_html((FIX / name).read_text(encoding="utf-8"), f"https://example.com/{name}")


def test_good_page_scores_high_and_bad_page_low():
    good = score_page(load("good.html"), TODAY)
    bad = score_page(load("bad.html"), TODAY)
    assert good.score >= 80, good.to_dict()
    assert bad.score <= 25, bad.to_dict()
    assert good.grade in ("A", "B") and bad.grade in ("D", "E")


def test_extraction_of_structure_and_metadata():
    p = load("good.html")
    assert p.h1 == ["BOAS surgery for English bulldogs in Los Angeles"]
    assert [s.heading for s in p.sections[1:]][:2] == ["What does BOAS surgery involve?", "How much does BOAS surgery cost in Los Angeles?"]
    assert p.author == "Dr. Antonio Pedraza"
    assert p.date_modified == "2026-08-20"
    assert "FAQPage" in p.schema_types and "MedicalWebPage" in p.schema_types
    assert p.tables == 1 and p.lists == 1
    assert len(p.authority_links) == 2          # rvc.ac.uk + avma.org
    assert p.internal_links == 3                # nav links + byline /about (counted over the whole document)
    assert p.byline_text and "Pedraza" in p.byline_text


def test_nav_footer_and_scripts_are_ignored():
    p = load("good.html")
    assert "Home" not in p.body_text and "©" not in p.body_text


def test_bad_page_recommendations_name_the_problems():
    r = score_page(load("bad.html"), TODAY)
    text = " ".join(r.recommendations)
    assert "JavaScript" in text            # readability
    assert "structured data" in text.lower()
    assert "H1" in text                     # two H1s
    assert "question" in text.lower()
    # ordered by points at stake: first recommendation must belong to a 15-point signal
    first = [s for s in r.signals if s.recommendation == r.recommendations[0]][0]
    assert first.max_points == 15


def test_freshness_windows():
    p = load("good.html")
    assert [s for s in score_page(p, date(2026, 9, 7)).signals if s.key == "freshness"][0].points == 5
    assert [s for s in score_page(p, date(2027, 6, 1)).signals if s.key == "freshness"][0].points == 3
    assert [s for s in score_page(p, date(2029, 1, 1)).signals if s.key == "freshness"][0].points == 0


def test_question_detection_english_and_spanish():
    assert _is_question("How much does it cost?")
    assert _is_question("Cuánto cuesta la cirugía BOAS")
    assert _is_question("Is BOAS surgery safe")
    assert not _is_question("Our services")


def test_parse_date_formats():
    assert _parse_date("2026-08-20") == date(2026, 8, 20)
    assert _parse_date("20/08/2026") == date(2026, 8, 20)
    assert _parse_date("2026-08-20T10:00:00Z") == date(2026, 8, 20)
    assert _parse_date("yesterday") is None


def test_grade_thresholds():
    assert grade(85) == "A" and grade(70) == "B" and grade(55) == "C" and grade(40) == "D" and grade(10) == "E"


def test_score_is_deterministic():
    p = load("good.html")
    assert score_page(p, TODAY).to_dict() == score_page(p, TODAY).to_dict()
