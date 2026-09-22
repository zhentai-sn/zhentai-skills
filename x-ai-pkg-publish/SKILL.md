---
name: x-ai-pkg-publish
description: AI 团队 Python 公共包发布流程。用户提到发包、发布版本、publish、要发 alpha/beta/rc/正式版、uv publish、准备发版、发个测试包 时，主动使用本 skill。覆盖预发布（Alpha/Beta/RC，dev 分支可发）和正式发布（master + tag 门禁）两种完整路径，含门禁检查、构建、上传到私有 Nexus、版本收尾。
---

# x-ai-pkg-publish — AI 团队发包流程

规范来源：`docs/sdd/01-发布流程.md`

## 两种路径速查

| 类型 | 允许分支 | git tag | 场景 |
|---|---|---|---|
| 预发布 `aN / bN / rcN` | dev 或 feat/* 均可 | 不需要 | 下游服务联调、集成测试 |
| 正式发布 | **必须 master** | **必须打** | 生产可用稳定版 |

---

## Step 1 — 确认发布类型

询问用户：这次发**预发布包**（Alpha / Beta / RC）还是**正式包**？

---

## Step 2 — 确认版本号

读取 `pyproject.toml` 中当前的 `version` 字段，然后根据类型引导：

**预发布：**
- 显示当前版本
- 询问后缀：`a`（Alpha）/ `b`（Beta）/ `rc`（RC）
- 自动推算序号：若当前已是 `0.1.0a1` 则建议 `0.1.0a2`；若当前是稳定版则建议 `0.1.0a1`
- 请用户确认最终版本号

**正式发布：**
- 若当前带预发布后缀（如 `0.1.0rc1`），建议去掉后缀（`0.1.0`）
- 若当前已是稳定版，询问升哪一位（PATCH / MINOR / MAJOR）
- 请用户确认最终版本号

---

## Step 3 — 门禁检查

**预发布门禁：**
```bash
uv run pytest
```
测试未全绿 → 停止，告知原因，等用户修复后重新发起。

**正式发布门禁（两项都要通过）：**
1. 检查当前分支：`git branch --show-current`
   - 不是 `master` → **拒绝**，提示先合并 PR 并切到 master
2. 运行 `uv run pytest`，同上

---

## Step 4 — CHANGELOG 确认

**预发布：** 提示可以在 `CHANGELOG.md` 的 `[未发布]` 节补记变更（非强制，等用户确认继续）。

**正式发布：** 必须操作，等用户确认完成后才继续：
> 请将 `CHANGELOG.md` 中的 `[未发布]` 内容归并到 `[X.Y.Z] — YYYY-MM-DD` 节，完成后告诉我。

---

## Step 5 — 更新版本号

将 `pyproject.toml` 中的 `version` 改为确认的新版本号。

---

## Step 6 — 构建

```bash
uv build
```

展示 `dist/` 下生成的 `.whl` 和 `.tar.gz` 文件名，确认无误再继续。

---

## Step 7 — 发布

```bash
uv publish
```

- 凭据从 `~/.netrc` 自动读取，无需用户输入
- 发布目标已在 `pyproject.toml` 的 `publish-url` 中配置（Nexus `pypi-hosted`）

发布成功后，告知用户下游服务的安装方式：

```bash
# 预发布（必须指定完整版本号）
uv add "x-ai-common==0.1.0a2"

# 正式发布
uv add "x-ai-common==0.1.0"
```

---

## Step 8 — 收尾

**预发布：**
```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: bump version to X.Y.ZaN"
```
不需要 tag，是否推送由用户决定。

**正式发布：**
```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
```
提示用户手动推送（需要 VPN / 网络）：
```bash
git push origin master --tags
```

---

## 中止规则

任何步骤失败（测试未过、分支不对、构建报错、发布失败）立即停止，说明原因，**不执行后续步骤**。不要绕过或忽略失败信息。
