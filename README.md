# LLM World Cup（LLM 世界杯）

[English](README.en.md) · 中文

> **Alpha 阶段**：同一道题，配置 2 / 4 / 8 个模型分别作答，匿名 Judge 通过双向复评的淘汰赛选出本场冠军，展示每场答案、判决理由、比分与耗时，并可导出完整比赛记录。

**重要边界**：冠军只代表「这道题、这次运行」里的偏好，**不是模型总体排名**，也不构成任何选型结论。模型输出具有随机性，同一对阵多次运行结果可能不同。

---

## 工作方式

1. **一次性生成**：每个参赛模型针对问题只回答一次，答案在整届比赛中缓存复用。
2. **匿名双向复评**：每对选手由裁判评判两次，A/B 顺序互换；只有两次判决指向同一候选才自动晋级。
3. **不随机造冠军**：出现平局、两次判决顺序矛盾、裁判返回格式错误或接口失败时，比赛停在 `needs_review`，等待人工复核，不会随机指定胜者。
4. **人工续赛**：在界面里为待定场次选择晋级者，提交后从当前轮继续后续淘汰。续赛必须沿用比赛时的非密钥配置；裁判模型、生成设置、评分维度或选手/模型发生变化时会被拒绝，避免混入来源不明的新一轮评判。
5. **导出**：每场比赛自动保存 JSON 与 Markdown 到 `.local/runs/`，也可在界面下载。

## 环境要求

- Python **3.11+**（开发与 CI 覆盖 3.11 / 3.12 / 3.13）
- 可访问的 OpenAI 兼容 Chat Completions 接口（远程 HTTPS，或本机 `localhost` 上的本地模型）
- 运行期依赖见 `requirements.txt`：`gradio==5.50.0`；测试与 lint 工具（`pytest`、`ruff`）见 `requirements-dev.txt`

## 安装

在**本项目目录内**创建独立虚拟环境（不要复用相邻项目的 `.venv`）：

```bash
git clone https://github.com/LYnini752/llm-worldcup.git
cd llm-worldcup
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

## 配置

1. 复制 `config.example.json`，按需修改（可在界面的配置框里直接编辑）。
2. **密钥只通过环境变量注入**，在配置里写变量名，不写明文 Key：

```bash
export PROVIDER_KEY="sk-..."
# 不同供应商可用不同变量名
export ANOTHER_PROVIDER_KEY="..."
```

### 配置字段

| 字段 | 说明 |
| --- | --- |
| `seed` | 整数随机种子，**只控制对阵洗牌**，不控制模型输出随机性 |
| `settings.temperature` | 参赛模型温度，默认 `0.3` |
| `settings.max_tokens` | 参赛模型最大生成 token，默认 `1500` |
| `settings.judge_temperature` | 裁判温度，默认 `0` |
| `settings.judge_max_tokens` | 裁判最大生成 token，默认 `1000` |
| `settings.timeout` | 单次请求超时（秒），默认 `120` |
| `settings.retries` | 瞬态错误（429 / 5xx / 网络超时）与裁判格式错误的重试次数，默认 `2` |
| `players[]` | 参赛模型：`name`（唯一展示名，不含 `||` 与换行）、`model`、`base_url`、`api_key_env` |
| `judge` | 裁判模型，字段同上；`name` 不能与参赛选手重名 |
| `rubric` | 四个维度权重，取值 0–100 且合计必须为 100 |

一个环境变量可以同时服务多个模型。`base_url` 不允许携带用户名密码、query 或 fragment；非 localhost 必须使用 HTTPS。

## 运行界面

```bash
python app.py
# 默认 http://127.0.0.1:7861 ，可用 PORT 环境变量改端口
```

- 输入问题 → 编辑配置 → **开始比赛**。
- 无密钥时可点 **离线预览合成演示**，查看界面样例（合成数据，不代表真实模型表现）。
- 待复核场次在「人工复核」折叠区选择晋级者 → **提交裁决并续赛**。
- **加载历史记录**可导入之前导出的 JSON，查看或继续复核。
- 导出文件位于 `.local/runs/<比赛ID>.json` 与 `.local/runs/<比赛ID>.md`。

## 测试与静态检查

```bash
pip install -r requirements-dev.txt   # 开发/测试额外包含 pytest、ruff
python -m pytest -q
ruff check .
```

测试使用伪造的调用桩（fake callable），**不发起真实网络请求，也不读取真实密钥**。覆盖：对阵轮次与答案缓存、顺序偏差暂停、失败不发冠军、人工续赛、配置校验、密钥不进入报告、裁判格式错误重试、客户端重试与 JSON 解析、导出往返、报告嵌套结构（轮次/场次/选手/答案/判决/人工裁决）导入校验、提示注入边界。

## 文档

- [架构说明](docs/ARCHITECTURE.md)：分层、比赛流程、报告 schema、安全边界与扩展点
- [贡献指南](CONTRIBUTING.md)：开发环境、本地检查、代码约定
- [安全策略](SECURITY.md)：密钥处理、不可信输入边界与已知限制
- [变更记录](CHANGELOG.md)、[第三方声明](NOTICE.md)、[发布清单](docs/RELEASE.md)

## 安全与隐私

- 配置、源码、日志、导出文件中**都不写入明文 Key**；错误信息也不会回显密钥。
- 答案与裁判文本被视为**不可信数据**：裁判提示词要求忽略答案中的指令、身份声称或打分要求，防止提示注入影响评判。
- `.env`、`config.json`、`.local/`、日志与密钥文件均已在 `.gitignore` 中排除，不会进入版本控制。
- 除你自行配置的模型接口外，本项目不向任何第三方上传比赛内容；比赛记录只保存在本地 `.local/` 目录。请自行确认所用供应商的数据留存与合规政策。

## 演示素材

`examples/` 下的 `demo_report.synthetic.json` / `.md` 是**手工编写的合成数据**，文件内标注 `"synthetic": true`，不代表任何真实模型表现。可用以下命令重新生成：

```bash
.venv/bin/python examples/generate_demo.py
```

## 项目结构

```
llm-worldcup/
├── app.py                  # Gradio 界面：展示、复核续赛、导出入口
├── tournament.py           # 赛制：生成、双向复评、暂停、人工续赛
├── provider.py             # 无第三方依赖的 OpenAI 兼容客户端（重试/校验/脱敏）
├── exporter.py             # 报告存取与 Markdown 导出
├── config.example.json     # 示例配置（密钥走环境变量）
├── examples/               # 合成演示素材（标注 synthetic）
├── docs/ARCHITECTURE.md    # 架构与报告 schema 说明
├── tests/                  # pytest 单元 / 集成 / 安全测试
├── .github/workflows/ci.yml# CI：多版本 Python 跑测试 + ruff
├── requirements.txt
├── requirements-dev.txt     # 开发额外依赖（pytest、ruff）
├── pyproject.toml
├── CONTRIBUTING.md / SECURITY.md / CHANGELOG.md / NOTICE.md
├── LICENSE                 # MIT
└── .gitignore
```

## 已知限制（Alpha）

- 未做并发裁判调度的可视化进度；长比赛按轮次推进。
- 裁判评分仅作记录，不做跨场汇总排名。
- 仅支持 OpenAI 兼容 Chat Completions 接口；流式输出未启用。
- 样式通过 `Blocks(css=...)` 注入；Gradio 6.0 移除该参数，升级时需迁移到新的样式注入方式。
- 真实 API 连通性、账号额度与界面端到端流程需要在有凭据的环境中验收；本仓库不附带任何真实凭据。

## 验证状态

本项目为软件 alpha。测试覆盖 2/4/8 强赛制、双向裁判、错误导入、原子人工裁决、导出与续赛配置一致性；仓库 Actions 提供 Python 3.11–3.13 验证结果。离线演示是合成报告，不请求模型。

新报告保存非密钥配置摘要，续赛会检查模型名称、裁判展示名与接口地址变化，不在报告中保存接口地址或 Key。旧报告仍能读取，但没有摘要的旧报告不能续赛，请重新开始比赛。摘要只用于一致性检查，不是报告真伪认证。

真实 API 连通性、额度及模型评判质量尚未测试。界面为中文，使用方法另有完整英文 README。

## 许可证

MIT，见 [LICENSE](LICENSE)。第三方依赖保留各自许可证。
