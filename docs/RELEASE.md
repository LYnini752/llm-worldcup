# Alpha 发布清单

目标：发布到**个人** GitHub 仓库。未配置仓库权限前，只在本地完成可发布产物；
不要推送到公司组织或其他账号。

## 发布前自检（本地）

- [ ] 独立虚拟环境：`python3 -m venv .venv && pip install -r requirements-dev.txt`
- [ ] 测试通过：`.venv/bin/python -m pytest -q`
- [ ] 静态检查通过：`.venv/bin/ruff check .`
- [ ] 界面可构造：`.venv/bin/python -c "import app; app.build_app()"`
- [ ] 伪造端到端：8 强比赛可完赛，JSON / Markdown 可往返加载（见 `tests/` 与 `examples/`）
- [ ] 密钥扫描：源码、示例配置、导出样例中无 `sk-...` / `Bearer ...` / 明文 `api_key`
- [ ] 暂存区不含 `.local/`、`.venv/`、`.env`、`config.json`、`HANDOFF.md`、`WORKLOG.md`、日志与密钥文件
- [ ] 合成演示文件带 `"synthetic": true`，不被当作真实模型表现引用

## 版本与记录

- [ ] 同步 `pyproject.toml` 版本号与 `CHANGELOG.md` 条目
- [ ] 确认 `README.md`、`SECURITY.md`、`NOTICE.md`、`docs/ARCHITECTURE.md` 链接有效
- [~] 第三方依赖许可证：2026-11-20 已在项目 `.venv` 全量审计，仅含 Apache-2.0 / MIT / BSD / MPL-2.0 / PSF / ISC 等宽松许可；打包分发前仍需对构建产物复核并保留各自声明

## 发布步骤（个人仓库）

1. 在个人 GitHub 新建空仓库（不自动生成 README / LICENSE，避免冲突）。
2. 配置本地提交身份（仅本仓库或全局按个人意愿），添加个人仓库远端。
3. 提交并打标签，例如 `v0.1.0a1`；推送 `main` 与标签。
4. 确认 CI（多版本 Python + ruff）在远端跑绿。
5. 在 Release 说明中写明：alpha、仅本题本场偏好、非总体排名、无内置鉴权、
   未附带真实凭据。

## 已知缺口（发布时如实标注）

- 真实 API 连通性、账号额度与端到端真实模型流程未在有凭据环境验收。
- 裁判模型自身的长上下文 / 越狱注入无法在客户端完全消除。
- Gradio 6.0 移除 `Blocks(css=...)` 参数；当前锁定 Gradio 5.50，升级时需迁移样式注入方式。
- 报告 schema 为 v1；后续结构变更需提升 `SCHEMA_VERSION` 并记录迁移策略。
- 续赛通过非密钥配置摘要检查模型、接口地址与裁判身份，并检查生成设置与评分维度；无摘要的旧报告可读取但不可续赛。摘要不是真伪认证。
