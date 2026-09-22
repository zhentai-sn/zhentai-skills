---
name: x-ai-gitflow
description: AI 团队现代 Git Flow 工作流。用于判断改动应直提 dev、创建 feat/fix/refactor 等短期主题分支、使用独立 git worktree、通过 MR 或 fast-forward 合入、从 dev 发布到 master、创建 release/hotfix 并回流修复。用户提到开分支、从哪个分支开始、能否直接提交 dev、功能分支、工作树、合并 dev/master、准备 release、线上 hotfix、分支命名、GitFlow 或分支治理时主动使用。不负责解决已经发生的 diverged、rebase/merge 冲突或 non-fast-forward；这些场景改用 x-ai-git-sync。
---

# x-ai-gitflow — 现代 Git Flow

采用 `dev + master`、短生命周期主题分支、按需 release 和生产 hotfix。允许低风险原子改动直提 `dev`；功能开发默认隔离到主题分支，并发任务使用独立 worktree。

## 规则优先级

按以下顺序执行：

1. 用户对当前任务的明确要求。
2. 仓库 `AGENTS.md`、`CLAUDE.md`、`CONTRIBUTING.md` 和发布文档。
3. 当前技能的默认策略。

先读取仓库规则。发现冲突时说明采用哪条仓库规则，不静默套用本技能。

## 第一步：只读诊断

先运行：

```bash
bash <skill-dir>/scripts/gitflow-status.sh
```

再确认：

- 工作区改动是否属于当前任务。
- 当前分支是否已被另一个 worktree 占用。
- `origin/dev`、`origin/master` 是否存在；若仓库使用 `main` 或其他名称，按仓库规则映射。
- 是否处于 merge、rebase、cherry-pick 或 detached HEAD。

工作区不干净且改动归属不明时停止。不要自动 stash、reset、checkout 覆盖或搬运他人改动。

## 第二步：选择工作路径

```text
低风险、范围小、单提交、可独立回滚
└─ 可直接提交 dev

功能、修复、重构、契约或数据库变化
└─ 创建短期主题分支
   ├─ 单任务且工作区独占：普通分支
   ├─ 多任务、多个 Agent 或多个会话：分支 + 独立 worktree
   ├─ 个人独立且低风险：验证后 ff-only 合入 dev
   └─ 高风险、多人协作或需审计：MR 合入 dev

正式发布
├─ 无冻结需求：dev → master → tag
└─ 需冻结或并行维护：dev → release/* → master → tag → 回流 dev

生产热修
└─ master → hotfix/* → master → tag → 回流 dev/活跃 release
```

边界不清时默认选择主题分支，代价低且隔离性更好。查看 [references/policy.md](references/policy.md) 获取详细分支矩阵、MR 门槛和发布配方。

## 路径 A：直接提交 `dev`

仅对低风险原子改动使用：

```bash
git fetch origin
git switch dev
git merge --ff-only origin/dev
```

确认脚本输出 `ahead=0`、`behind=0` 且工作区干净后再实施改动。若 `dev` 已有未推送提交，先确认其归属，不要把未知提交夹带进本次 push。

运行与风险相称的验证，再按仓库规范提交：

```bash
git push origin dev
```

如果 `dev` 与 `origin/dev` 已分叉，停止直提并改用 `x-ai-git-sync`。禁止为完成直提而 force push。

## 路径 B：主题分支

先同步远端引用，再从远端集成分支创建：

```bash
git fetch origin
git switch -c feat/<slug> origin/dev
```

按改动性质选择前缀：

- `feat/<slug>`：新增功能。
- `fix/<slug>`：非生产缺陷修复。
- `refactor/<slug>`：行为不变的结构调整。
- `docs/<slug>`、`test/<slug>`、`chore/<slug>`：独立文档、测试或维护工作。

使用小写 kebab-case；仓库要求 issue ID 或版本号时遵循仓库格式。

### 并发任务使用 worktree

从任一干净管理工作区执行：

```bash
git fetch origin
git worktree add ../<repo>-<slug> -b feat/<slug> origin/dev
```

一个任务、一个分支、一个 worktree。不要让多个会话写同一 worktree，也不要在主工作区反复切换其他会话正在使用的分支。

## 合入 `dev`

先完成 lint、测试、文档或验收门禁，再 `fetch`。

个人未发布的主题分支默认重放到最新集成分支：

```bash
git rebase origin/dev
```

已推送并被他人使用的分支不要擅自 rebase；调用 `x-ai-git-sync` 评估。

无需 MR 时，在持有 `dev` 的工作区执行：

```bash
git switch dev
git merge --ff-only origin/dev
git merge --ff-only <topic-branch>
git push origin dev
```

`--ff-only` 失败表示历史不满足线性合入条件。不要临时改成 force push；重新诊断并决定 rebase、merge 或 MR。

以下情况默认使用 MR：

- 多人共同开发或分支已共享。
- 数据库、鉴权、安全、支付、隐私、公共 API 或部署基础设施变化。
- 改动跨多个服务、共享热点文件或需要产品/架构审阅。
- 仓库保护规则、发布规则或用户明确要求 MR。

## 发布与 hotfix

处理正式发布、`release/*` 或 `hotfix/*` 时，必须读取 [references/policy.md](references/policy.md) 的对应章节。

保持以下硬约束：

- `master` 只保存生产发布历史，不作为日常开发分支。
- `release/*` 只接收发布阻断修复，不继续开发新功能。
- `hotfix/*` 必须从最新生产 `master` 创建。
- 发布修复必须回流 `dev`；存在活跃 release 时同时回流。
- Tag 指向实际生产提交；版本号、Tag 和发布授权必须明确。

创建或推送 Tag、合入 `master`、删除远端分支属于发布或外部状态变更，只在用户授权范围内执行。

## 共享历史安全

- 禁止对 `dev`、`master`、`release/*` 和共享主题分支执行 force push。
- 未发布的个人主题提交可 rebase；共享提交优先 merge 或按团队约定处理。
- 共享分支上的错误使用追加修复或 `git revert`。
- 不用 `git reset --hard`、`git checkout --` 或删除工作树来处理归属不明的改动。
- push 遇到 non-fast-forward 时重新 fetch 并调用 `x-ai-git-sync`，不要绕过保护。

## 收尾

合入并确认远端成功后：

1. 检查目标分支包含预期提交。
2. 确认验证结果与部署/发布状态。
3. 经确认后删除已合并的本地主题分支和 worktree。
4. 删除远端分支前确认不再被协作者或流水线使用。
5. 报告分支、提交、合入方式、验证和远端同步结果。
