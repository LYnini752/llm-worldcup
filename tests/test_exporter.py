import json

import pytest

from exporter import load_report, save_report, to_markdown, write_markdown


def _sample_report():
    return {
        "id": "demo-0001",
        "schema_version": 1,
        "created_at": "2026-11-19T12:00:00+00:00",
        "question": "什么是过拟合？",
        "seed": 42,
        "rubric": {"correctness": 40, "relevance": 25, "completeness": 20, "clarity": 15},
        "status": "complete",
        "answers": {
            "Alpha": {"text": "答案 A", "seconds": 1.2, "usage": {"total_tokens": 30},
                      "char_count": 6},
            "Beta": {"text": "答案 B", "seconds": 0.9, "usage": {"total_tokens": 28},
                     "char_count": 6},
        },
        "rounds": [
            [{"id": "m1", "players": ["Alpha", "Beta"], "winner": "Alpha",
              "review_required": None, "error": None,
              "judgments": [
                  {"order": ["Alpha", "Beta"], "winner": "A", "reason": "更清楚",
                   "scores": {"A": 82, "B": 74}, "seconds": 0.4},
                  {"order": ["Beta", "Alpha"], "winner": "B", "reason": "更清楚",
                   "scores": {"A": 74, "B": 82}, "seconds": 0.4},
              ]}]
        ],
        "winner": "Alpha",
        "settings": {},
        "judge_model": "judge-model",
        "limitations": "Single-question bracket preference, not an overall model ranking.",
    }


def test_markdown_contains_answers_reasons_and_timings():
    md = to_markdown(_sample_report())
    assert "Alpha" in md and "Beta" in md
    assert "更清楚" in md
    assert "1.2s" in md and "0.4s" in md
    assert "82 : 74" in md


def test_markdown_contains_manual_decision():
    report = _sample_report()
    report["rounds"][0][0]["manual_decision"] = {
        "decided_by": "manual", "winner": "Alpha",
        "note": "复核后更清楚", "resolved_at": "2026-11-19T13:00:00+00:00",
    }
    md = to_markdown(report)
    assert "人工裁决" in md and "Alpha" in md and "复核后更清楚" in md


def test_load_rejects_unknown_schema(tmp_path):
    report = _sample_report()
    report["schema_version"] = 99
    path = tmp_path / "old.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        load_report(path)


def test_save_rejects_traversal_id_json_and_markdown(tmp_path):
    report = _sample_report()
    report["id"] = "../escaped"
    with pytest.raises(ValueError):
        save_report(report, tmp_path)
    with pytest.raises(ValueError):
        write_markdown(report, tmp_path)
    assert not list(tmp_path.parent.glob("escaped.*"))


def test_save_rejects_absolute_id(tmp_path):
    report = _sample_report()
    report["id"] = "/tmp/abs/escaped"
    with pytest.raises(ValueError):
        save_report(report, tmp_path)
    with pytest.raises(ValueError):
        write_markdown(report, tmp_path)


def test_save_rejects_unsafe_id_characters(tmp_path):
    for bad in ["a/b", "a\\b", "..", ".hidden", "a b", "a|b"]:
        report = _sample_report()
        report["id"] = bad
        with pytest.raises(ValueError):
            save_report(report, tmp_path)


def test_load_rejects_missing_or_typed_wrong_fields(tmp_path):
    report = _sample_report()
    del report["question"]
    bad = tmp_path / "missing.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        load_report(bad)

    report = _sample_report()
    report["answers"] = []
    bad = tmp_path / "typed.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        load_report(bad)

    report = _sample_report()
    report["id"] = "../nope"
    bad = tmp_path / "id.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        load_report(bad)


def test_load_rejects_null_match_in_rounds(tmp_path):
    report = _sample_report()
    report["rounds"] = [[None]]
    bad = tmp_path / "null-match.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="match must be an object"):
        load_report(bad)


def test_load_rejects_malformed_players(tmp_path):
    report = _sample_report()
    report["rounds"][0][0]["players"] = ["OnlyOne"]
    bad = tmp_path / "players.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="two name strings"):
        load_report(bad)


def test_load_rejects_non_dict_answer(tmp_path):
    report = _sample_report()
    report["answers"]["Alpha"] = ["not", "an", "object"]
    bad = tmp_path / "answer.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Answer"):
        load_report(bad)


def test_load_rejects_malformed_judgment(tmp_path):
    report = _sample_report()
    report["rounds"][0][0]["judgments"][0]["winner"] = "C"
    bad = tmp_path / "verdict.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="winner"):
        load_report(bad)


def test_load_rejects_list_manual_decision(tmp_path):
    report = _sample_report()
    report["rounds"][0][0]["manual_decision"] = ["invalid"]
    bad = tmp_path / "decision-list.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="manual_decision"):
        load_report(bad)


def test_load_rejects_manual_decision_winner_outside_players(tmp_path):
    report = _sample_report()
    report["rounds"][0][0]["manual_decision"] = {
        "decided_by": "manual", "winner": "Nobody",
        "note": None, "resolved_at": "2026-11-19T13:00:00+00:00",
    }
    bad = tmp_path / "decision-winner.json"
    bad.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="manual_decision winner"):
        load_report(bad)


def test_save_load_round_trip(tmp_path):
    report = _sample_report()
    json_path = save_report(report, tmp_path)
    md_path = write_markdown(report, tmp_path)
    loaded = load_report(json_path)
    assert loaded["winner"] == "Alpha"
    assert md_path.exists()
    assert "secret" not in json.dumps(loaded)
