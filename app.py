"""Gradio interface for the LLM World Cup bracket."""
import html
import json
import os
from pathlib import Path

import gradio as gr

from exporter import load_report, save_report, write_markdown
from tournament import resolve_review, run_tournament, unresolved_matches

ROOT = Path(__file__).resolve().parent
MAX_REVIEW_SLOTS = 4

STATUS_LABELS = {
    "complete": "已完赛",
    "needs_review": "待人工复核",
    "generation_failed": "答案生成失败",
    "running": "进行中",
}

STATUS_CLASSES = {
    "complete": "badge ok",
    "needs_review": "badge warn",
    "generation_failed": "badge error",
    "running": "badge info",
}

_ROUND_NAMES = {
    2: ["决赛"],
    4: ["半决赛", "决赛"],
    8: ["1/4 决赛", "半决赛", "决赛"],
}


def _round_label(total, index):
    names = _ROUND_NAMES.get(total, [])
    if 0 <= index < len(names):
        return names[index]
    return f"第 {index + 1} 轮"


def _esc(text):
    return html.escape(str(text if text is not None else ""))


def _render_answer(name, answer, highlight=False):
    cls = "answer winner" if highlight else "answer"
    if not answer:
        return f"<div class='{cls}'><b>{_esc(name)}</b><p class='muted'>无记录</p></div>"
    if "error" in answer:
        return (f"<div class='{cls} error'><b>{_esc(name)}</b>"
                f"<p class='muted'>调用失败：{_esc(answer['error'])}</p></div>")
    meta = []
    if answer.get("seconds") is not None:
        meta.append(f"{answer['seconds']}s")
    if answer.get("char_count") is not None:
        meta.append(f"{answer['char_count']} 字")
    usage = answer.get("usage", {})
    if usage.get("total_tokens") is not None:
        meta.append(f"{usage['total_tokens']} tokens")
    meta_text = f" <span class='muted'>({_esc(' · '.join(meta))})</span>" if meta else ""
    body = _esc(answer["text"]).replace("\n", "<br>")
    return f"<div class='{cls}'><b>{_esc(name)}</b>{meta_text}<p>{body}</p></div>"


def _verdict_line(verdict):
    order_a, order_b = verdict["order"]
    scores = verdict.get("scores", {})
    winner_label = {"A": order_a, "B": order_b, "tie": "平局"}.get(verdict.get("winner"))
    return (
        f"<li>复评顺序 {_esc(order_a)} / {_esc(order_b)}："
        f"判决 <b>{_esc(winner_label)}</b>，比分 {_esc(scores.get('A'))} : {_esc(scores.get('B'))}，"
        f"耗时 {_esc(verdict.get('seconds'))}s<br>"
        f"<span class='muted'>理由：{_esc(verdict.get('reason', ''))}</span></li>"
    )


def render(report):
    if not report:
        return "<p class='muted'>尚未开始比赛。</p>"
    status = report.get("status", "")
    status_label = STATUS_LABELS.get(status, status)
    badge = STATUS_CLASSES.get(status, "badge info")
    total = len(report.get("answers", {}))
    winner = report.get("winner") or "待定"
    parts = [
        (f"<h2><span class='{badge}'>{_esc(status_label)}</span>"
         f"冠军：<b>{_esc(winner)}</b></h2>")
    ]
    if report.get("question"):
        parts.append(
            f"<div class='question'><b>问题：</b>"
            f"{_esc(report['question']).replace(chr(10), '<br>')}</div>"
        )
    if total:
        parts.append(f"<p class='muted'>参赛模型 {total} 个 · 裁判 {_esc(report.get('judge_model', '—'))}</p>")

    for index, matches in enumerate(report.get("rounds", [])):
        parts.append(f"<h3>{_esc(_round_label(total, index))}</h3><div class='round'>")
        for match in matches:
            a, b = match["players"]
            match_winner = match.get("winner")
            parts.append("<article class='match'>")
            parts.append(f"<div class='players'>{_esc(a)} × {_esc(b)}</div>")
            parts.append("<div class='answers'>")
            parts.append(_render_answer(a, report.get("answers", {}).get(a),
                                        highlight=(match_winner == a)))
            parts.append(_render_answer(b, report.get("answers", {}).get(b),
                                        highlight=(match_winner == b)))
            parts.append("</div>")
            if match.get("error"):
                parts.append(f"<p class='error'>错误：{_esc(match['error'])}</p>")
            if match.get("review_required"):
                parts.append(f"<p class='warn'>待复核：{_esc(match['review_required'])}</p>")
            decision = match.get("manual_decision")
            if isinstance(decision, dict):
                note = f"，备注：{_esc(decision['note'])}" if decision.get("note") else ""
                parts.append(
                    f"<p class='muted'>人工裁决：{_esc(decision.get('winner'))}"
                    f"（{_esc(decision.get('resolved_at'))}）{note}</p>"
                )
            parts.append(f"<p>晋级：<b>{_esc(match_winner or '待定')}</b></p>")
            if match.get("judgments"):
                parts.append("<ul>" + "".join(_verdict_line(v) for v in match["judgments"]) + "</ul>")
            parts.append("</article>")
        parts.append("</div>")

    parts.append(f"<p class='muted'>说明：{_esc(report.get('limitations', ''))}</p>")
    return "".join(parts)


def _review_panel(report):
    pending = _pending(report)
    if not pending:
        return "<p class='muted'>当前没有待复核场次。</p>"
    answers = report.get("answers", {})
    blocks = []
    for match in pending:
        a, b = match["players"]
        blocks.append(
            f"<article class='match review'><div class='players'>"
            f"#{_esc(match['id'])} {_esc(a)} × {_esc(b)}</div><div class='answers'>"
            f"{_render_answer(a, answers.get(a))}{_render_answer(b, answers.get(b))}"
            f"</div></article>"
        )
    return "".join(blocks)


def _parse_config(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise gr.Error(f"配置不是合法 JSON：{exc.msg}（第 {exc.lineno} 行）") from None


def _persist(report):
    json_path = save_report(report)
    md_path = write_markdown(report)
    return str(json_path), str(md_path)


def start(question, raw_config):
    if not question or not question.strip():
        raise gr.Error("请先输入要比较的问题")
    config = _parse_config(raw_config)
    try:
        report = run_tournament(question, config)
    except ValueError as exc:
        raise gr.Error(str(exc)) from None
    json_path, md_path = _persist(report)
    return (render(report), report, report, [json_path, md_path],
            *_review_updates(report), _review_panel(report))


def _pending(report):
    return unresolved_matches(report) if report else []


def _review_updates(report):
    pending = _pending(report)
    updates = []
    for i in range(MAX_REVIEW_SLOTS):
        if i < len(pending):
            match = pending[i]
            a, b = match["players"]
            label = f"#{match['id']} {a} × {b}"
            updates.append(gr.update(visible=True, label=label, choices=[a, b], value=None))
        else:
            updates.append(gr.update(visible=False, label="—", choices=[], value=None))
    return updates


def apply_review(report, raw_config, *choices):
    if not report:
        raise gr.Error("当前没有可复核的比赛记录")
    config = _parse_config(raw_config)
    pending = _pending(report)
    decisions = {}
    for match, choice in zip(pending, choices):
        if choice:
            decisions[f"{match['players'][0]}||{match['players'][1]}"] = choice
    try:
        report = resolve_review(report, decisions, config)
    except ValueError as exc:
        raise gr.Error(str(exc)) from None
    json_path, md_path = _persist(report)
    return (render(report), report, report, [json_path, md_path],
            *_review_updates(report), _review_panel(report))


def load_history(file_obj):
    if not file_obj:
        raise gr.Error("请先选择一份比赛记录 JSON")
    path = file_obj.name if hasattr(file_obj, "name") else file_obj
    try:
        report = load_report(path)
        outputs = (render(report), report, report, [],
                   *_review_updates(report), _review_panel(report))
    except (ValueError, OSError, json.JSONDecodeError, TypeError,
            AttributeError, KeyError, IndexError) as exc:
        raise gr.Error(f"无法加载比赛记录：{exc}") from None
    return outputs


def load_demo():
    """Load the bundled synthetic report for an offline UI preview (no API call)."""
    demo_path = ROOT / "examples" / "demo_report.synthetic.json"
    report = load_report(demo_path)
    return (render(report), report, report, [],
            *_review_updates(report), _review_panel(report))


def build_app():
    with gr.Blocks(title="LLM World Cup", theme=gr.themes.Soft(), css=(
        ".round{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0}"
        "article.match{border:1px solid #ccc;border-radius:14px;padding:18px;flex:1;min-width:280px}"
        ".answers{display:flex;gap:12px;flex-wrap:wrap}"
        ".answer{flex:1;min-width:220px;background:#f7f7f8;border-radius:10px;padding:12px}"
        ".answer p{margin:8px 0 0;white-space:normal}"
        ".muted{color:#666;font-size:13px}"
        ".error{color:#b00020}"
        ".warn{color:#8a5a00}"
        ".question{background:#f0f4ff;border-radius:10px;padding:12px;margin:10px 0}"
        "ul{margin:8px 0}"
        ".badge{display:inline-block;border-radius:999px;padding:2px 12px;font-size:13px;margin-right:8px}"
        ".badge.ok{background:#e6f4ea;color:#137333}"
        ".badge.warn{background:#fef7e0;color:#8a5a00}"
        ".badge.error{background:#fce8e6;color:#b00020}"
        ".badge.info{background:#e8f0fe;color:#1967d2}"
        ".answer.winner{border:1.5px solid #137333;background:#f2faf4}"
        ".match.review{border-style:dashed}"
        "@media (max-width:640px){.round{flex-direction:column}.answer{min-width:0}}"
    )) as demo:
        gr.Markdown("# LLM 世界杯\n同一道题，每位模型只回答一次，匿名双向复评淘汰。**冠军只代表本题本场偏好，不是模型总体排名。**")

        question = gr.Textbox(label="你的问题", lines=3, value="怎样向初学者解释过拟合？请举一个具体例子。")
        gr.Examples(examples=[[q] for q in json.loads((Path(__file__).parent / "examples/questions.json").read_text(encoding="utf-8"))], inputs=question, label="示例问题（真实比赛需要配置 API）")
        with gr.Accordion("参赛模型与裁判配置（密钥只走环境变量，不写入配置或导出文件）", open=True):
            config = gr.Code(value=(ROOT / "config.example.json").read_text(encoding="utf-8"),
                             language="json", label="配置 JSON")

        with gr.Row():
            button = gr.Button("开始比赛", variant="primary")
            load_btn = gr.Button("加载历史记录")
            demo_btn = gr.Button("离线预览合成演示")
        history = gr.File(label="历史比赛 JSON", file_types=[".json"], visible=False)

        review_slots = []
        with gr.Accordion("人工复核（平局 / 顺序偏差 / 接口错误时使用）", open=False):
            gr.Markdown("为每一场待定对决选择晋级者；未选择的场次仍保持待复核。提交后将从当前轮继续比赛。")
            review_panel = gr.HTML()
            for _ in range(MAX_REVIEW_SLOTS):
                review_slots.append(gr.Dropdown(visible=False, choices=[], label="—"))
            resume_btn = gr.Button("提交裁决并续赛", variant="secondary")

        bracket = gr.HTML()
        report_state = gr.State()
        report_json = gr.JSON(label="完整比赛记录（含答案、判决与耗时）")
        downloads = gr.File(label="导出文件（JSON + Markdown）")

        outputs = [bracket, report_state, report_json, downloads, *review_slots, review_panel]
        button.click(start, [question, config], outputs)
        load_btn.click(lambda: gr.update(visible=True), None, history)
        history.change(load_history, history, outputs)
        demo_btn.click(load_demo, None, outputs)
        resume_btn.click(apply_review, [report_state, config, *review_slots], outputs)

        gr.Markdown("出现平局、顺序偏差或接口错误时暂停比赛，不会随机指定冠军。")
    return demo


if __name__ == "__main__":
    build_app().queue().launch(
        server_name="127.0.0.1",
        server_port=int(os.getenv("PORT", "7861")),
        share=False,
    )
