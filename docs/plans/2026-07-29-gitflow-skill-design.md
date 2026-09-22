# 现代 Git Flow 技能设计

## 目标与边界

新增 `x-ai-gitflow`，为AI 团队提供统一、可执行的现代 Git 分支工作流。它保留团队现有的 `dev` 集成分支与 `master` 生产分支，采用短生命周期主题分支，并仅在发布冻结或并行维护时创建 `release/*`。

该技能负责分支选择、创建、同步、合入、发布回流和工作树隔离；不重复实现分叉处理、提交信息生成、PR/MR 创建或具体语言包发布。分叉交给 `x-ai-git-sync`，发布细节交给对应发布技能，仓库内 `AGENTS.md` 和用户明确要求优先。

## 工作流选择

不采用经典 GitFlow 的常驻 `develop`、`release` 和长生命周期功能分支。经典 GitFlow 更适合固定发布周期，持续交付场景下容易增加分支漂移和合并成本。

也不采用只有 `main` 的纯 GitHub Flow，因为团队已有 `dev` 集成、`master` 发布以及 test/pre/prod 多环境链路。

采用现代 GitLab Flow 变体：

- `master` 保存生产发布历史。
- `dev` 作为日常集成分支，允许直接 commit/push，不强制 MR。
- 功能、修复和重构默认使用短生命周期主题分支。
- `release/*` 按需存在，不作为每次发布的必经分支。
- `hotfix/*` 从 `master` 创建，发布后回流 `dev` 和活跃 `release/*`。

## 分支与工作树策略

| 分支 | 基线 | 用途 | 合入目标 |
| --- | --- | --- | --- |
| `dev` | 长期分支 | 日常集成；允许低风险原子改动直提 | `master` 或 `release/*` |
| `master` | 长期分支 | 生产发布历史 | 不作为日常开发目标 |
| `feat/*` | `origin/dev` | 功能开发 | `dev` |
| `fix/*` | `origin/dev` | 非生产缺陷修复 | `dev` |
| `refactor/*` | `origin/dev` | 结构重构 | `dev` |
| `docs/*`、`chore/*`、`test/*` | `origin/dev` | 独立维护改动 | `dev` |
| `release/vX.Y.Z` | `dev` | 发布冻结、稳定化、并行版本维护 | `master`，随后回流 `dev` |
| `hotfix/vX.Y.Z` | `master` | 线上紧急修复 | `master`，随后回流 `dev` 和活跃 release |

工作树不是分支类型。单任务可在普通 checkout 中使用主题分支；多个 Agent、多个任务或多个功能并发时，一个主题分支对应一个独立 `git worktree`，禁止多个会话共享同一工作区写入。

## `dev` 直接提交边界

`dev` 不强制 MR，但直接提交必须满足：

- 改动低风险、范围小、可独立回滚。
- 提交前已 `fetch`，本地 `dev` 可 fast-forward 到 `origin/dev`，不存在未处理分叉。
- 工作区没有混入其他任务的改动。
- 已运行与改动相称的 lint、测试或文档校验。
- 使用普通 push，禁止 force push。

文档、拼写、小配置和低风险维护通常可以直提。功能开发、结构重构、Bug 修复、数据库或 API 契约变化默认创建主题分支；高风险、多人协作、共享热点文件或需要审计的改动使用 MR。

## 合入与历史策略

- 主题分支保持短生命周期，提交表达完整、可回滚的实现单元。
- 个人未发布的主题分支可 rebase 到最新 `origin/dev`。
- 已共享或被他人依赖的提交不改写历史；调用 `x-ai-git-sync` 判断 rebase 或 merge。
- 无需 MR 的个人主题分支在验证后，优先以 `--ff-only` 合入 `dev`，保留线性历史和 implementation-unit commits。
- 需要评审的改动通过 MR 合入；仓库既有 merge/squash 策略优先，技能不全局强制 squash。
- 进入共享分支后的错误使用追加修复或 `git revert`，不用 reset 或 force push 改写历史。

## 发布与热修

正常发布有两条路径：

1. 无冻结需求：验证 `dev` 后合入 `master`，打带注释的版本 Tag。
2. 需要冻结或并行维护：从 `dev` 创建 `release/vX.Y.Z`，只接受发布阻断修复；验收后合入 `master` 并打 Tag，再将发布修复回流 `dev`。

线上热修从最新 `master` 创建 `hotfix/vX.Y.Z`。验收后合入 `master`、打 Tag，再将同一修复回流 `dev` 和仍活跃的 `release/*`，避免后续版本重新引入问题。

## 技能结构

- `SKILL.md`：触发范围、仓库诊断、分支决策树和核心执行流程。
- `references/policy.md`：分支矩阵、直接提交边界、发布与热修配方、异常处理。
- `scripts/gitflow-status.sh`：只读输出仓库根、当前分支、工作区状态、上游、领先/落后、远端默认分支和活跃长期分支。
- `agents/openai.yaml`：技能展示名称、短描述和默认提示词。

README 同步增加技能清单和本地安装命令。

## 安全与失败处理

- 所有变更前先识别仓库规则、工作区状态、当前分支和远端关系。
- 工作区不干净且改动归属不明时停止，不自动 stash、reset 或覆盖。
- `dev`、`master`、`release/*` 和共享主题分支禁止 force push。
- rebase/merge 冲突由 `x-ai-git-sync` 处理；未解决前不继续合入或推送。
- 创建 Tag、合入 `master`、发布和删除远端分支前确认目标版本与授权范围。
- 仓库规则与本技能冲突时，以仓库规则为准并说明偏差。

## 验证标准

- 技能目录通过 `quick_validate.py`。
- 状态脚本通过临时 Git 仓库的干净、脏工作区、有上游和无上游场景测试。
- README 技能清单和安装命令包含 `x-ai-gitflow`。
- 技能能明确回答直提 `dev`、主题分支、worktree、MR、release 和 hotfix 的选择。
- 技能与 `x-ai-git-sync`、`x-ai-pkg-publish` 的职责不冲突。
- 本机安装入口指向仓库源目录。
- 设计与实现分别提交，提交信息不包含模型署名，并推送到远端。
