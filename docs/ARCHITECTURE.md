# 架构说明

## 分层概览

```
app.py  ──  Gradio 界面：输入问题与配置、渲染对阵/答案/判决、人工复核、导出入口
   │
   ├── tournament.py  ──  赛制核心：配置校验、答案生成缓存、双向复评、暂停与人工续赛
   │
   ├── provider.py    ──  无第三方依赖的 OpenAI 兼容 Chat Completions 客户端
   │
   └── exporter.py    ──  报告 JSON 存取、schema 版本校验、Markdown 导出
```

依赖方向单向向下：界面不直接发 HTTP；赛制通过可注入的 `call` 函数调用模型，
默认实现是 `provider.chat`，测试时替换为伪造桩。

## 一次比赛的流程

1. **校验**：`validate_config` 检查选手数量（2/4/8）、名称唯一、裁判不重名、
   模型规格、评分权重合计 100、种子、温度与 token / 超时 / 重试参数。
2. **答案生成**：`_generate_answers` 并发调用每位选手一次，结果写入
   `report["answers"]` 并在整届比赛缓存复用；单个失败只记录为该选手的 `error`，
   不中断其他选手。任一选手失败，报告状态置为 `generation_failed`。
3. **轮次淘汰**：`_play_round` 把当前晋级名单两两配对；每对由裁判复评两次，
   A/B 顺序互换（`judge_pair`）。`_resolve_pair` 对照两次判决：
   - 两次指向同一候选 → 自动晋级；
   - 两次都平局，或两次顺序矛盾 → 写入 `review_required`，停在 `needs_review`；
   - 接口或格式异常 → 记录为该场 `error`，等待人工复核。
4. **人工续赛**：`resolve_review` 先校验全部裁决（场次键、胜者、备注类型）与配置
   一致性，通过后再写入结构化 `manual_decision`（决定者、胜者、备注、UTC 时间戳），
   然后从当前轮继续后续淘汰；任一裁决无效则输入报告保持原样。续赛沿用原非密钥配置，
   裁判模型 / 设置 / 评分维度 / 选手模型与已保存报告不一致时拒绝。
5. **导出**：`save_report` 落 JSON，`write_markdown` 落 Markdown；报告 ID 必须是安全
   slug，输出路径解析后强制包含在输出目录内；界面同时提供下载。

## 报告 schema（`schema_version: 1`）

顶层字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 比赛 UUID |
| `schema_version` | 报告结构版本；加载时校验，未知版本拒绝 |
| `created_at` | UTC ISO 时间戳 |
| `question` | 本题问题原文 |
| `seed` | 仅控制对阵洗牌的随机种子 |
| `rubric` | 四个评分维度权重 |
| `status` | `running` / `complete` / `needs_review` / `generation_failed` |
| `answers` | `选手名 → {text, seconds, model, usage, char_count}` 或 `{error}` |
| `rounds` | 各轮场次列表；每场含 `players / winner / review_required / error / judgments[] / manual_decision?` |
| `winner` | 本场冠军；未决为 `null` |
| `settings` | 合并后的运行参数 |
| `judge_model` | 裁判模型标识 |
| `limitations` | 边界声明：仅本题本场偏好，不是总体排名 |

`judgments[]` 单条：`order`（本次复评顺序）、`winner`（A/B/tie）、`reason`、
`scores{A,B}`、`usage`、`seconds`。

## 安全边界

- **密钥**：只通过环境变量解析；配置拒绝字面量 `api_key` 与 URL 内嵌凭据；
  报告、导出、错误信息、日志均不写入 Key；`mask_private` 可对文本做打码。
- **不可信输入**：选手答案与裁判文本不进入系统提示；裁判系统提示明确要求忽略
  候选答案中的指令、身份声称与打分要求；候选内容只放在用户载荷 JSON 中。
- **取值防护**：请求消息形状与总长校验，响应 4 MB 上限；比分、判决、理由均做
  结构与取值校验，非法判决触发重试或转入复核。

## 测试策略

- `tests/test_tournament.py`：赛制、缓存、顺序偏差、失败不发冠军、人工续赛、配置校验。
- `tests/test_provider.py`：客户端重试、Retry-After、尺寸/形状守卫、响应异常分支、脱敏。
- `tests/test_exporter.py`：导出往返、Markdown 内容、schema 版本校验。
- `tests/test_app_integration.py`：直接驱动真实界面事件处理器（打桩网络层），
  覆盖开始完赛、偏见续赛、历史加载、非法配置与空问题。
- `tests/test_security.py`：密钥不进入报告/导出/落盘文件，注入短语不进入系统提示。

测试不发起真实网络请求，也不读取真实密钥。

## 扩展点

- **新供应商协议**：在 `provider.py` 增加客户端函数，保持返回
  `{text, seconds, usage, model}` 契约，赛制无需改动。
- **新裁判策略**：替换 `judge_pair` / `_resolve_pair` 的对照规则；
  双复评一致性判定集中在 `_resolve_pair`。
- **报告格式**：结构变更时提升 `SCHEMA_VERSION`，并在 `exporter.load_report`
  与 CHANGELOG 中记录迁移策略。
