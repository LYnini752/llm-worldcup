import copy
import json
from pathlib import Path

import pytest

from provider import validate_model
from tournament import resolve_review, run_tournament, unresolved_matches

CONFIG = json.loads((Path(__file__).parents[1] / "config.example.json").read_text())


def fake(spec, messages, **kwargs):
    if spec["name"] != "Judge":
        return {"text": spec["name"], "model": spec["model"], "seconds": 0.1,
                "usage": {"total_tokens": 12}}
    data = json.loads(messages[-1]["content"])
    winner = "A" if data["candidate_A"] < data["candidate_B"] else "B"
    return {"text": json.dumps({"winner": winner, "reason": "fixture lexical order",
                                "scores": {"A": 80, "B": 70}}), "seconds": 0.2, "usage": {}}


def test_eight_players_seven_matches_and_cached_answers():
    c = copy.deepcopy(CONFIG)
    c["players"] = [dict(c["players"][0], name=f"Player {i}") for i in range(8)]
    calls = []

    def tracked(*args, **kwargs):
        calls.append(args[0]["name"])
        return fake(*args, **kwargs)

    report = run_tournament("Question", c, tracked)
    assert report["winner"] == "Player 0"
    assert [len(r) for r in report["rounds"]] == [4, 2, 1]
    assert len(calls) == 22  # 8 answers + 14 judgments (7 matches x 2)


def test_two_player_final_completes():
    report = run_tournament("Question", CONFIG, fake)
    assert report["status"] == "complete"
    assert [len(r) for r in report["rounds"]] == [1]
    assert report["winner"] in [p["name"] for p in CONFIG["players"]]


def test_four_player_bracket_auto_advances():
    c = copy.deepcopy(CONFIG)
    c["players"] = [dict(c["players"][0], name=f"Player {i}") for i in range(4)]
    report = run_tournament("Question", c, fake)
    assert report["status"] == "complete"
    assert [len(r) for r in report["rounds"]] == [2, 1]
    assert report["winner"] == "Player 0"


def test_position_bias_stops_tournament():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)
    assert report["status"] == "needs_review"
    assert report["winner"] is None
    assert unresolved_matches(report)


def test_failure_does_not_award_champion():
    def failed(*args, **kwargs):
        raise RuntimeError("Unavailable")

    report = run_tournament("Question", CONFIG, failed)
    assert report["status"] == "generation_failed"
    assert report["winner"] is None


def test_answer_error_masks_bearer_token():
    secret = "Bear" + "er abcdef1234567890"

    def flaky(spec, messages, **kwargs):
        if spec["name"] != "Judge":
            raise RuntimeError(f"call failed: {secret}")
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, flaky)
    for answer in report["answers"].values():
        if "error" in answer:
            assert secret not in answer["error"]
            assert "***" in answer["error"]


def test_judge_error_masks_bearer_token():
    secret = "Bear" + "er zyxw9876543210"

    def judge_fails(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            raise RuntimeError(f"upstream said {secret}")
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, judge_fails)
    for matches in report["rounds"]:
        for match in matches:
            if match.get("error"):
                assert secret not in match["error"]
                assert "***" in match["error"]


def test_config_rejects_credentials_in_url():
    with pytest.raises(ValueError):
        validate_model({"name": "x", "model": "x",
                        "base_url": "https://secret@example.org/v1"})


def test_manual_review_resumes_and_finishes_bracket():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)
    assert report["status"] == "needs_review"
    pending = unresolved_matches(report)
    a, b = pending[0]["players"]
    decisions = {f"{a}||{b}": a}

    resumed = resolve_review(report, decisions, CONFIG, fake)
    assert resumed["status"] == "complete"
    assert resumed["winner"] == a


def test_four_player_resume_plays_final_round():
    c = copy.deepcopy(CONFIG)
    c["players"] = [dict(c["players"][0], name=f"P{i}") for i in range(4)]

    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", c, biased)
    assert report["status"] == "needs_review"
    pending = unresolved_matches(report)
    assert len(pending) == 2
    decisions = {f"{m['players'][0]}||{m['players'][1]}": m["players"][0] for m in pending}

    resumed = resolve_review(report, decisions, c, fake)
    assert resumed["status"] == "complete"
    assert resumed["winner"] in {m["players"][0] for m in pending}
    assert [len(r) for r in resumed["rounds"]] == [2, 1]


def test_manual_decision_records_audit_trail():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)
    pending = unresolved_matches(report)
    a, b = pending[0]["players"]
    decisions = {f"{a}||{b}": {"winner": a, "note": "复核后表达更清楚"}}

    resumed = resolve_review(report, decisions, CONFIG, fake)
    assert resumed["schema_version"] == 1
    decision = resumed["rounds"][0][0]["manual_decision"]
    assert decision["decided_by"] == "manual"
    assert decision["winner"] == a
    assert decision["note"] == "复核后表达更清楚"
    assert decision["resolved_at"]


def test_reject_invalid_manual_decision():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)
    a, b = report["rounds"][0][0]["players"]
    with pytest.raises(ValueError):
        resolve_review(report, {f"{a}||{b}": "Nobody"}, CONFIG, fake)


def test_review_is_atomic_when_later_decision_invalid():
    c = copy.deepcopy(CONFIG)
    c["players"] = [dict(c["players"][0], name=f"P{i}") for i in range(4)]

    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", c, biased)
    pending = unresolved_matches(report)
    assert len(pending) == 2
    first, second = pending
    decisions = {
        f"{first['players'][0]}||{first['players'][1]}": first["players"][0],
        f"{second['players'][0]}||{second['players'][1]}": "Nobody",
    }
    with pytest.raises(ValueError):
        resolve_review(report, decisions, c, fake)

    # The first valid decision must not have been applied either.
    for match in report["rounds"][0]:
        assert match["winner"] is None
        assert "manual_decision" not in match
    assert report["status"] == "needs_review"


def test_reject_resume_with_changed_judge_model():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)
    changed = copy.deepcopy(CONFIG)
    changed["judge"]["model"] = "judge-v2"
    with pytest.raises(ValueError, match="judge model"):
        resolve_review(report, {}, changed, fake)
    assert report["status"] == "needs_review"


def test_reject_resume_with_changed_settings_or_rubric():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)

    changed_settings = copy.deepcopy(CONFIG)
    changed_settings["settings"]["temperature"] = 0.9
    with pytest.raises(ValueError, match="settings"):
        resolve_review(report, {}, changed_settings, fake)

    changed_rubric = copy.deepcopy(CONFIG)
    changed_rubric["rubric"]["correctness"] = 50
    changed_rubric["rubric"]["relevance"] = 15
    with pytest.raises(ValueError, match="rubric"):
        resolve_review(report, {}, changed_rubric, fake)


def test_reject_resume_with_changed_player_model():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)
    changed = copy.deepcopy(CONFIG)
    changed["players"][0]["model"] = "model-a-v2"
    with pytest.raises(ValueError, match="player model"):
        resolve_review(report, {}, changed, fake)


def test_reject_unknown_decision_key():
    def biased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "A", "reason": "bias",
                                        "scores": {"A": 80, "B": 70}})}
        return fake(spec, messages, **kwargs)

    report = run_tournament("Question", CONFIG, biased)
    with pytest.raises(ValueError):
        resolve_review(report, {"Ghost||Other": "Ghost"}, CONFIG, fake)


def test_question_length_guarded():
    with pytest.raises(ValueError):
        run_tournament("   ", CONFIG, fake)
    with pytest.raises(ValueError):
        run_tournament("x" * 12001, CONFIG, fake)


def test_config_validation_rejects_bad_shapes():
    base = copy.deepcopy(CONFIG)

    bad_count = copy.deepcopy(base)
    bad_count["players"].append(bad_count["players"][0])
    with pytest.raises(ValueError):
        run_tournament("Q", bad_count, fake)

    dup = copy.deepcopy(base)
    dup["players"][1]["name"] = dup["players"][0]["name"]
    with pytest.raises(ValueError):
        run_tournament("Q", dup, fake)

    bad_rubric = copy.deepcopy(base)
    bad_rubric["rubric"] = {"correctness": 40, "relevance": 30,
                            "completeness": 20, "clarity": 20}
    with pytest.raises(ValueError):
        run_tournament("Q", bad_rubric, fake)

    judge_collide = copy.deepcopy(base)
    judge_collide["judge"]["name"] = base["players"][0]["name"]
    with pytest.raises(ValueError):
        run_tournament("Q", judge_collide, fake)

    bad_seed = copy.deepcopy(base)
    bad_seed["seed"] = "not-an-int"
    with pytest.raises(ValueError):
        run_tournament("Q", bad_seed, fake)

    delimiter = copy.deepcopy(base)
    delimiter["players"][0]["name"] = "Alpha||Beta"
    with pytest.raises(ValueError):
        run_tournament("Q", delimiter, fake)

    newline = copy.deepcopy(base)
    newline["judge"]["name"] = "Judge\nOther"
    with pytest.raises(ValueError):
        run_tournament("Q", newline, fake)


def test_report_never_contains_secret_or_authorization():
    c = copy.deepcopy(CONFIG)
    c["players"][0]["api_key_env"] = "TEST_WORLDCUP_KEY"
    report = run_tournament("Question", c, fake)
    serialized = json.dumps(report, ensure_ascii=False)
    assert "Bearer" not in serialized
    assert "api_key" not in serialized
    assert "TEST_WORLDCUP_KEY" not in serialized


def test_malformed_verdict_is_retried_then_marked_for_review():
    calls = {"n": 0}

    def flaky_judge(spec, messages, **kwargs):
        if spec["name"] != "Judge":
            return fake(spec, messages, **kwargs)
        calls["n"] += 1
        return {"text": "not json at all"}

    report = run_tournament("Question", CONFIG, flaky_judge)
    assert report["status"] == "needs_review"
    assert calls["n"] >= 2  # retried before giving up
    assert report["rounds"][0][0]["error"]


@pytest.mark.parametrize("field", ["base_url", "name"])
def test_resume_rejects_changed_judge_identity_without_mutation(field):
    def tied(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "tie", "reason": "fixture", "scores": {"A": 50, "B": 50}})}
        return fake(spec, messages, **kwargs)
    report = run_tournament("Question", CONFIG, tied)
    original = copy.deepcopy(report)
    changed = copy.deepcopy(CONFIG)
    changed["judge"][field] = "https://different.example/v1" if field == "base_url" else "New judge"
    with pytest.raises(ValueError, match="identity or endpoint"):
        resolve_review(report, {}, changed, fake)
    assert report == original
    assert CONFIG["judge"]["base_url"] not in json.dumps(report)


def test_resume_allows_credential_rotation_and_provider_model_alias():
    def aliased(spec, messages, **kwargs):
        if spec["name"] == "Judge":
            return {"text": json.dumps({"winner": "tie", "reason": "fixture", "scores": {"A": 50, "B": 50}})}
        return dict(fake(spec, messages, **kwargs), model="resolved-model-version")
    report = run_tournament("Question", CONFIG, aliased)
    changed = copy.deepcopy(CONFIG)
    changed["judge"]["api_key_env"] = "ROTATED_KEY"
    pending = unresolved_matches(report)[0]
    resumed = resolve_review(report, {pending["id"]: pending["players"][0]}, changed, fake)
    assert resumed["status"] == "complete"


def test_legacy_report_without_provenance_cannot_resume():
    report = run_tournament("Question", CONFIG, fake)
    report["status"] = "needs_review"
    report.pop("config_fingerprint")
    with pytest.raises(ValueError, match="legacy report"):
        resolve_review(report, {}, CONFIG, fake)
