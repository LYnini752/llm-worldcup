# 示例数据 / Sample data

这些原创合成材料按 MIT 许可发布，不包含真实模型表现或用户问题。

- `questions.json`：点击界面的示例问题即可填入输入框；开始比赛仍会调用你配置的真实模型。
- `demo_report.synthetic.json` / `.md`：点“离线预览合成演示”可立即查看完整赛程、答案与冠军，不需要 Key。结果为手工合成，不能当作模型排名。

The question presets are original examples. The completed report is a synthetic fixture, not a real benchmark. Use the offline preview button to explore it without API credentials.

打开网页即显示免 Key 的预制合成赛程。真实比赛可以先用 2 个模型；同一服务商的多个模型与裁判可以共用一个 API Key，通过相同的 `api_key_env` 引用。
The page displays the synthetic bracket by default, without credentials. For live matches, start with two models. Models and the judge can share one provider key through the same `api_key_env`.
