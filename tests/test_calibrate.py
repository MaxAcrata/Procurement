"""Threshold calibration over labeled review pairs (S3)."""

from __future__ import annotations

import json


def test_calibrate_prints_table_and_recommended_threshold(tmp_path):
    from typer.testing import CliRunner
    import main as main_mod
    from core.article_match import calculate_score

    labels = tmp_path / "match_review.json"
    hi_a, hi_b = "71B3750", "71B3750"
    lo_a, lo_b = "RT110GR.1/000/600", "RT110GR.1/128/150"
    assert calculate_score(hi_a, hi_b) >= 0.9
    assert calculate_score(lo_a, lo_b) <= 0.5
    labels.write_text(json.dumps([
        {"article_a": hi_a, "article_b": hi_b, "decision": "confirmed"},
        {"article_a": lo_a, "article_b": lo_b, "decision": "rejected"},
        {"article_a": "71B3751", "article_b": "71B3751", "decision": "confirmed"},
    ]), encoding="utf-8")

    result = CliRunner().invoke(main_mod.app, ["calibrate", "--labels", str(labels)])
    assert result.exit_code == 0, result.output
    assert "precision" in result.output.lower()
    assert "recommended" in result.output.lower()


def test_calibrate_apply_rewrites_config_threshold(tmp_path):
    from typer.testing import CliRunner
    import main as main_mod

    labels = tmp_path / "match_review.json"
    labels.write_text(json.dumps([
        {"article_a": "71B3750", "article_b": "71B3750", "decision": "confirmed"},
        {"article_a": "XYZ-1", "article_b": "XYZ-9", "decision": "rejected"},
    ]), encoding="utf-8")
    cfg_src = tmp_path / "config.py"
    cfg_src.write_text(
        "class ArticleMatchConfig:\n    threshold: float = 0.75\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main_mod.app,
        ["calibrate", "--labels", str(labels), "--apply", "--config", str(cfg_src)],
    )
    assert result.exit_code == 0, result.output
    text = cfg_src.read_text(encoding="utf-8")
    assert "threshold" in text and "0.75" not in text
