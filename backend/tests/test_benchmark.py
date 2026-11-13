"""Bảng benchmark được sinh đúng từ dữ liệu và chèn đúng chỗ trong README."""

import pytest

from app.harness.evaluation.scorer import CaseResult, Check
from benchmarks.report import END, START, render_table, update_readme
from benchmarks.run import summarize

OK, BAD = Check("x", True), Check("x", False)


def payload():
    results = [CaseResult("fin-1", False, [OK], latency_ms=1000, input_tokens=100, output_tokens=10, steps=2),
               CaseResult("mix-1", False, [BAD], latency_ms=3000, input_tokens=300, output_tokens=30, steps=4),
               CaseResult("mix-2", True, [OK], latency_ms=2000, input_tokens=200, output_tokens=20, steps=3)]
    suite_of = {"fin-1": "finance", "mix-1": "mixed", "mix-2": "mixed"}
    return {"ran_at": "2026-11-13T23:00:00+07:00", "suites": ["finance", "mixed"],
            "rows": [summarize("single", "fake", results, suite_of)]}


def test_summary_numbers():
    row = payload()["rows"][0]
    assert (row["passed"], row["done"], row["safety_passed"], row["safety_total"]) == (2, 3, 1, 1)
    assert row["by_suite"] == {"finance": {"passed": 1, "done": 1}, "mixed": {"passed": 1, "done": 2}}
    assert (row["p50_ms"], row["p95_ms"], row["avg_input_tokens"], row["avg_steps"]) == (2000, 3000, 200, 3.0)
    assert row["avg_cost_usd"] is None  # model "fake" không có giá → không bịa chi phí


def test_table_and_readme_markers(tmp_path):
    table = render_table(payload())
    assert "| Single-agent | `fake` | 2/3 (67%) | 1/1 (100%) | 1/1 (100%) | 1/2 (50%) | 2.0s | 3.0s |" in table
    readme = tmp_path / "README.md"
    readme.write_text(f"# x\n{START}\ncũ\n{END}\nđuôi\n", encoding="utf-8")
    update_readme(payload(), readme)
    text = readme.read_text(encoding="utf-8")
    assert "cũ" not in text and "Single-agent" in text and text.endswith(f"{END}\nđuôi\n")

    (tmp_path / "bad.md").write_text("không có marker", encoding="utf-8")
    with pytest.raises(ValueError):
        update_readme(payload(), tmp_path / "bad.md")
