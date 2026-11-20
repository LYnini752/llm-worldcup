# 贡献指南

感谢你关注 LLM 世界杯。本项目是个人开源的 alpha 工具，目标是在**不泄露密钥、不编造真实模型结果**的前提下，把「同一道题、多模型匿名淘汰赛」这件事做稳、做清楚。

## 开发环境

在项目目录内创建**独立**虚拟环境，不要复用相邻项目或系统里的 `.venv`：

```bash
cd llm-worldcup
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

## 本地检查

提交前必须三项都通过：

```bash
.venv/bin/python -m pytest -q     # 全部测试
.venv/bin/ruff check .            # 静态检查
.venv/bin/python -c "import app; app.build_app()"   # 界面可构造
```

测试使用伪造调用桩，**不发起真实网络请求、不读取真实密钥**；新增行为请同步补充测试。

## 代码约定

- 核心赛制与 HTTP 客户端尽量保持标准库依赖；新增第三方依赖请先在 issue / 讨论中说明理由。
- 配置校验失败对外抛出 `ValueError`；网络、HTTP、响应格式问题抛出 `ProviderError`。
- 模型答案与裁判文本一律视为**不可信数据**：不要把它们拼进系统提示，不要据此执行指令、路径或网络请求。
- 密钥只从环境变量读取；任何新的日志、报告、导出、错误信息都不得包含 Key、Bearer 令牌或环境变量值。
- 中文面向用户文案保持简洁；代码注释与提交信息可用英文。

## 提交与分支

- 从 `main` 切出特性分支，提交信息清晰描述「做了什么、为什么」。
- 一个提交聚焦一件事；重构、测试、文档尽量分开。
- 不要在提交里夹带 `.env`、`config.json`、`.local/`、真实比赛记录或任何凭据。

## 报告问题

- 功能建议、缺陷请用 GitHub Issue；安全问题请先阅读 [SECURITY.md](SECURITY.md)，不要在公开 Issue 贴真实 Key。
- 复现报告请注明：Python 版本、操作系统、使用的接口类型、配置中**脱敏后**的模型字段，以及相关报错（敏感值先打码）。

## 范围边界

- 冠军仅代表本题本场偏好，不要在文档或 UI 中把结果表述为模型总体排名。
- 本仓库不附带真实凭据，也不接受需要硬编码供应商 Key 的改动。
