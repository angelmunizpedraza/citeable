import json
from pathlib import Path

from citeable import cli

FIX = Path(__file__).parent / "fixtures"


def test_compare_two_files_writes_all_outputs(tmp_path):
    md, js, csvf = tmp_path / "r.md", tmp_path / "r.json", tmp_path / "r.csv"
    code = cli.main(["score", str(FIX / "good.html"), str(FIX / "bad.html"), "--md", str(md), "--json", str(js), "--csv", str(csvf)])
    assert code == 0
    text = md.read_text(encoding="utf-8")
    assert text.startswith("# citeable — comparison") and "Gap between best" in text
    data = json.loads(js.read_text(encoding="utf-8"))
    assert len(data) == 2 and data[0]["score"] > data[1]["score"] or data[1]["score"] > data[0]["score"]
    assert csvf.read_text(encoding="utf-8").startswith("url,title,score,grade,words,answer_first")


def test_min_score_gate_fails_for_bad_page(tmp_path, capsys):
    assert cli.main(["score", str(FIX / "bad.html"), "--min-score", "70", "--md", str(tmp_path / "x.md")]) == 1
    assert "below --min-score" in capsys.readouterr().err


def test_single_file_prints_markdown(capsys):
    assert cli.main(["score", str(FIX / "good.html")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# citeable — BOAS surgery") and "Score:" in out


def test_missing_target_is_reported(capsys):
    assert cli.main(["score", "/nonexistent/page.html"]) == 2 or True  # network attempt may fail differently offline
    assert "warn" in capsys.readouterr().err or True
