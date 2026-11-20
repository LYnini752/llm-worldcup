"""Integration tests driving the real Gradio event handlers with a stubbed network layer.

These do not start an HTTP server and do not call any real model API. They exercise
the same handler functions wired to the UI: start, manual review resume, history
load, and config error reporting.
"""
import copy
import json
from pathlib import Path

import gradio as gr
import pytest

import app as app_module
import exporter
import tournament
from tournament import unresolved_matches

CONFIG = json.loads((Path(__file__).parents[1] / "config.example.json").read_text())


def make_fake(bias=False):
    def fake(spec, messages, **kwargs):
        if spec["name"] != "Judge":
            return {"text": f"答案-{spec['name']}", "seconds": 0.5,
                    "usage": {"total_tokens": 10}}
        if bias:
            verdict = {"winner": "A", "reason": "偏见顺序", "scores": {"A": 80, "B": 70}}
        else:
            data = json.loads(messages[-1]["content"])
            winner = "A" if data["candidate_A"] < data["candidate_B"] else "B"
            verdict = {"winner": winner, "reason": "对照理由", "scores": {"A": 80, "B": 70}}
        return {"text": json.dumps(verdict), "seconds": 0.3}

    return fake


@pytest.fixture
def isolated_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, "RUNS_DIR", tmp_path)
    return tmp_path


def test_start_completes_and_exports(isolated_runs, monkeypatch):
    monkeypatch.setattr(tournament, "chat", make_fake())
    html, report, report_json, files, *slots, panel = app_module.start(
        "解释过拟合", json.dumps(CONFIG))

    assert report["status"] == "complete"
    assert report["winner"]
    assert report["winner"] in html
    assert "答案-" in html and "0.5s" in html
    assert report_json == report
    assert len(files) == 2
    assert all(Path(f).exists() for f in files)
    assert all(s["visible"] is False for s in slots)
    assert "没有待复核" in panel


def test_review_resume_flow(isolated_runs, monkeypatch):
    monkeypatch.setattr(tournament, "chat", make_fake(bias=True))
    _html, report, _, _, *slots, panel = app_module.start("解释过拟合", json.dumps(CONFIG))

    assert report["status"] == "needs_review"
    pending = unresolved_matches(report)
    assert len(pending) == 1
    assert slots[0]["visible"] is True
    assert pending[0]["players"][0] in panel
    choice = pending[0]["players"][0]

    _html2, report2, _, files2, *slots2, panel2 = app_module.apply_review(
        report, json.dumps(CONFIG), choice, None, None, None)

    assert report2["status"] == "complete"
    assert report2["winner"] == choice
    assert all(s["visible"] is False for s in slots2)
    assert "待复核" in panel2
    assert len(files2) == 2


def test_load_history_round_trip(isolated_runs, monkeypatch):
    monkeypatch.setattr(tournament, "chat", make_fake())
    _, report, _, files, *_, _panel = app_module.start("问题", json.dumps(CONFIG))

    html2, loaded, loaded_json, _files2, *_, _panel2 = app_module.load_history(files[0])
    assert loaded["id"] == report["id"]
    assert loaded_json == loaded
    assert report["winner"] in html2


def test_empty_question_raises_gr_error():
    with pytest.raises(gr.Error):
        app_module.start("   ", json.dumps(CONFIG))


def test_load_demo_preview_offline():
    html, report, report_json, files, *_slots, _panel = app_module.load_demo()
    assert report["status"] == "complete"
    assert report["winner"]
    assert report["winner"] in html
    assert report_json == report
    assert files == []
    assert "synthetic" in json.dumps(report)


def test_invalid_json_config_raises_gr_error():
    with pytest.raises(gr.Error):
        app_module.start("问题", "{不是合法 JSON")


def test_load_history_rejects_malformed_file(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(gr.Error):
        app_module.load_history(str(bad))


def test_load_history_rejects_unknown_schema(tmp_path):
    report = json.loads((Path(__file__).parents[1] / "examples" /
                         "demo_report.synthetic.json").read_text())
    report["schema_version"] = 99
    bad = tmp_path / "old.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(gr.Error):
        app_module.load_history(str(bad))


def test_load_history_rejects_nested_null_match(tmp_path):
    report = json.loads((Path(__file__).parents[1] / "examples" /
                         "demo_report.synthetic.json").read_text())
    report["rounds"] = [[None]]
    bad = tmp_path / "nested.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(gr.Error):
        app_module.load_history(str(bad))


def test_load_history_rejects_list_manual_decision(tmp_path):
    report = json.loads((Path(__file__).parents[1] / "examples" /
                         "demo_report.synthetic.json").read_text())
    report["rounds"][0][0]["manual_decision"] = ["invalid"]
    bad = tmp_path / "decision-list.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(gr.Error):
        app_module.load_history(str(bad))


def test_invalid_config_shape_raises_gr_error(isolated_runs, monkeypatch):
    monkeypatch.setattr(tournament, "chat", make_fake())
    bad = copy.deepcopy(CONFIG)
    bad["players"].append(bad["players"][0])
    with pytest.raises(gr.Error):
        app_module.start("问题", json.dumps(bad))
