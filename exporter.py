"""Persist and render match reports. Reports never contain API keys."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / ".local" / "runs"
SCHEMA_VERSION = 1

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_REQUIRED_TOP_LEVEL = {
    "id": str,
    "schema_version": int,
    "question": str,
    "answers": dict,
    "rounds": list,
    "status": str,
    "rubric": dict,
}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_answers(answers):
    for name, answer in answers.items():
        if not isinstance(name, str):
            raise ValueError("Answer keys must be player name strings")
        if not isinstance(answer, dict):
            raise ValueError(f"Answer for {name!r} must be an object")
        if "error" in answer:
            if not isinstance(answer["error"], str):
                raise ValueError(f"Answer error for {name!r} must be a string")
            continue
        if not isinstance(answer.get("text"), str):
            raise ValueError(f"Answer text for {name!r} must be a string")
        if "seconds" in answer and answer["seconds"] is not None and not _is_number(answer["seconds"]):
            raise ValueError(f"Answer seconds for {name!r} must be a number")
        if "model" in answer and answer["model"] is not None and not isinstance(answer["model"], str):
            raise ValueError(f"Answer model for {name!r} must be a string")
        if "char_count" in answer and not isinstance(answer["char_count"], int):
            raise ValueError(f"Answer char_count for {name!r} must be an integer")
        if "usage" in answer and not isinstance(answer["usage"], dict):
            raise ValueError(f"Answer usage for {name!r} must be an object")


def _validate_manual_decision(match):
    decision = match.get("manual_decision")
    if decision is None:
        return
    if not isinstance(decision, dict):
        raise ValueError("manual_decision must be an object")
    if decision.get("winner") not in match["players"]:
        raise ValueError("manual_decision winner must be one of the match players")
    if decision.get("note") is not None and not isinstance(decision["note"], str):
        raise ValueError("manual_decision note must be a string or null")
    for field in ("decided_by", "resolved_at"):
        if field in decision and not isinstance(decision[field], str):
            raise ValueError(f"manual_decision {field} must be a string")


def _validate_judgments(judgments):
    if not isinstance(judgments, list):
        raise ValueError("Match judgments must be a list")
    for verdict in judgments:
        if not isinstance(verdict, dict):
            raise ValueError("Each judgment must be an object")
        order = verdict.get("order")
        if not (isinstance(order, list) and len(order) == 2
                and all(isinstance(x, str) for x in order)):
            raise ValueError("Judgment order must be a list of two player names")
        if verdict.get("winner") not in ("A", "B", "tie"):
            raise ValueError("Judgment winner must be A, B or tie")
        if not isinstance(verdict.get("reason"), str):
            raise ValueError("Judgment reason must be a string")
        scores = verdict.get("scores")
        if not isinstance(scores, dict) or set(scores) != {"A", "B"}:
            raise ValueError("Judgment scores must contain A and B")
        if any(not _is_number(v) for v in scores.values()):
            raise ValueError("Judgment scores must be numbers")
        if "seconds" in verdict and verdict["seconds"] is not None and not _is_number(verdict["seconds"]):
            raise ValueError("Judgment seconds must be a number")
        if "usage" in verdict and not isinstance(verdict["usage"], dict):
            raise ValueError("Judgment usage must be an object")


def _validate_rounds(rounds):
    if not isinstance(rounds, list):
        raise ValueError("Rounds must be a list")
    for matches in rounds:
        if not isinstance(matches, list):
            raise ValueError("Each round must be a list of matches")
        for match in matches:
            if not isinstance(match, dict):
                raise ValueError("Each match must be an object")
            players = match.get("players")
            if not (isinstance(players, list) and len(players) == 2
                    and all(isinstance(x, str) for x in players)):
                raise ValueError("Match players must be two name strings")
            if "id" in match and not isinstance(match["id"], str):
                raise ValueError("Match id must be a string")
            for field in ("winner", "review_required", "error"):
                if field in match and not (match[field] is None or isinstance(match[field], str)):
                    raise ValueError(f"Match {field!r} must be a string or null")
            _validate_judgments(match.get("judgments", []))
            _validate_manual_decision(match)


def _validate_report_shape(report):
    """Reject non-dict reports and enforce the minimal v1 field set/types."""
    if not isinstance(report, dict):
        raise ValueError("Not a valid match report")
    for field, expected in _REQUIRED_TOP_LEVEL.items():
        if field not in report:
            raise ValueError(f"Match report is missing field: {field}")
        if not isinstance(report[field], expected) or isinstance(report[field], bool):
            raise ValueError(f"Match report field {field!r} has an invalid type")
    if report["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"Unsupported report schema version: {report['schema_version']!r}")
    if not _SAFE_ID_RE.match(report["id"]):
        raise ValueError("Match report id must be a safe slug (letters, digits, '-' or '_')")
    if "winner" in report and not (report["winner"] is None or isinstance(report["winner"], str)):
        raise ValueError("Report winner must be a string or null")
    if "settings" in report and not isinstance(report["settings"], dict):
        raise ValueError("Report settings must be an object")
    if "judge_model" in report and not (report["judge_model"] is None or isinstance(report["judge_model"], str)):
        raise ValueError("Report judge_model must be a string or null")
    if "seed" in report and (not isinstance(report["seed"], int) or isinstance(report["seed"], bool)):
        raise ValueError("Report seed must be an integer")
    if "created_at" in report and not isinstance(report["created_at"], str):
        raise ValueError("Report created_at must be a string")
    if "limitations" in report and not (report["limitations"] is None or isinstance(report["limitations"], str)):
        raise ValueError("Report limitations must be a string or null")
    _validate_answers(report["answers"])
    _validate_rounds(report["rounds"])


def _output_path(report, directory, suffix):
    directory = Path(directory) if directory else RUNS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    root = directory.resolve()
    candidate = (root / f"{report['id']}{suffix}").resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Resolved report path escapes the output directory")
    return candidate


def save_report(report, directory=None):
    _validate_report_shape(report)
    path = _output_path(report, directory, ".json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_report(path):
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_report_shape(report)
    return report


def _answer_brief(report, name):
    answer = report.get("answers", {}).get(name, {})
    if "error" in answer:
        return f"_(调用失败：{answer['error']})_"
    seconds = answer.get("seconds")
    usage = answer.get("usage", {})
    tokens = usage.get("total_tokens")
    meta = []
    if seconds is not None:
        meta.append(f"{seconds}s")
    if tokens is not None:
        meta.append(f"{tokens} tokens")
    meta_text = f"  _({' · '.join(meta)})_" if meta else ""
    return f"{answer.get('text', '')}{meta_text}"


def to_markdown(report):
    lines = [
        f"# LLM 世界杯 · {report.get('status', 'unknown')}",
        "",
        f"- 比赛 ID: `{report.get('id')}`",
        f"- 报告版本: schema v{report.get('schema_version', '?')}",
        f"- 生成时间: {report.get('created_at')}",
        f"- 冠军: **{report.get('winner') or '待定'}**",
        f"- 随机种子（仅控制对阵）: {report.get('seed')}",
        "",
        "## 问题",
        "",
        report.get("question", ""),
        "",
        "## 评分维度",
        "",
        json.dumps(report.get("rubric", {}), ensure_ascii=False),
        "",
    ]
    for round_index, matches in enumerate(report.get("rounds", []), 1):
        lines.append(f"## 第 {round_index} 轮")
        lines.append("")
        for match in matches:
            a, b = match["players"]
            lines.append(f"### {a} × {b}")
            lines.append("")
            lines.append(f"**{a} 的答案**")
            lines.append("")
            lines.append(_answer_brief(report, a))
            lines.append("")
            lines.append(f"**{b} 的答案**")
            lines.append("")
            lines.append(_answer_brief(report, b))
            lines.append("")
            if match.get("error"):
                lines.append(f"- 错误: {match['error']}")
            if match.get("review_required"):
                lines.append(f"- 待复核: {match['review_required']}")
            decision = match.get("manual_decision")
            if isinstance(decision, dict):
                note = f"，备注：{decision['note']}" if decision.get("note") else ""
                lines.append(
                    f"- 人工裁决：**{decision.get('winner')}**"
                    f"（{decision.get('resolved_at')}）{note}"
                )
            lines.append(f"- 晋级: **{match.get('winner') or '待定'}**")
            lines.append("")
            for verdict in match.get("judgments", []):
                order_a, order_b = verdict["order"]
                scores = verdict.get("scores", {})
                lines.append(
                    f"- 复评顺序 {order_a} / {order_b}："
                    f"判决 {verdict.get('winner')}，"
                    f"比分 {scores.get('A')} : {scores.get('B')}，"
                    f"耗时 {verdict.get('seconds')}s"
                )
                lines.append(f"  - 理由：{verdict.get('reason', '')}")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"> 说明：{report.get('limitations', '')}")
    lines.append("")
    return "\n".join(lines)


def write_markdown(report, directory=None):
    _validate_report_shape(report)
    path = _output_path(report, directory, ".md")
    path.write_text(to_markdown(report), encoding="utf-8")
    return path
