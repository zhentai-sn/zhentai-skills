# 现代 Git Flow 策略参考

## 目录

- [分支矩阵](#分支矩阵)
- [`dev` 直接提交门槛](#dev-直接提交门槛)
- [主题分支与 MR 门槛](#主题分支与-mr-门槛)
- [工作树策略](#工作树策略)
- [正常发布](#正常发布)
- [Release 分支](#release-分支)
- [生产 Hotfix](#生产-hotfix)
- [同步、回滚与异常](#同步回滚与异常)
- [设计依据](#设计依据)

## 分支矩阵

| 分支 | 从哪里创建 | 允许内容 | 默认合入目标 | 历史约束 |
| --- | --- | --- | --- | --- |
| `dev` | 长期分支 | 集成代码、低风险直提 | `master` 或 `release/*` | 禁止 force push |
| `master` | 长期分支 | 已发布或即将发布的生产代码 | 无 | 禁止日常直提和 force push |
| `feat/*` | `origin/dev` | 单一功能 | `dev` | 短生命周期 |
| `fix/*` | `origin/dev` | 非生产缺陷 | `dev` | 短生命周期 |
| `refactor/*` | `origin/dev` | 行为不变的结构调整 | `dev` | 短生命周期 |
| `docs/*` | `origin/dev` | 独立文档工作 | `dev` | 短生命周期 |
| `test/*` | `origin/dev` | 独立测试工作 | `dev` | 短生命周期 |
| `chore/*` | `origin/dev` | 工具、依赖和维护 | `dev` | 短生命周期 |
| `release/vX.Y.Z` | 最新 `dev` | 稳定化和发布阻断修复 | `master`、`dev` | 禁止新功能和 force push |
| `hotfix/vX.Y.Z` | 最新 `master` | 单一生产紧急修复 | `master`、`dev`、活跃 release | 禁止无关改动和 force push |

若仓库使用 `main` 代替 `master`，或使用 `develop` 代替 `dev`，映射名称但保持职责不变。仓库明文规则优先。

## `dev` 直接提交门槛

同时满足以下条件才直提：

- 改动范围小，最好只有一个可独立回滚的提交。
- 不改变数据库结构、公共 API、鉴权、安全边界或部署拓扑。
- 不需要跨成员协作或专门评审。
- 同步后本地 `dev` 与 `origin/dev` 均为 `ahead=0`、`behind=0`。
- 工作区没有其他任务的文件。
- 已执行必要验证。

典型适用：

- 文档、拼写、注释。
- 明确的小配置修正。
- 低风险构建脚本维护。
- 已确认行为不变的微小测试修复。

任一条件不满足时创建主题分支。

## 主题分支与 MR 门槛

主题分支解决的是工作隔离；MR 解决的是评审、门禁和审计。创建主题分支不等于必须创建 MR。

个人独立改动可在以下条件下 ff-only 合入 `dev`：

- 分支未被其他人依赖。
- 改动风险低或中等。
- 验证全部通过。
- 仓库不要求 MR。
- 合入前已基于最新 `origin/dev`。

以下情况使用 MR：

- 两人及以上参与。
- 数据库迁移、公共契约、权限、安全、隐私或生产基础设施。
- 大范围重构或热点文件。
- 需要 CI、Code Owner、产品或架构批准。
- 需要保留审阅讨论和决策记录。

默认不强制 squash。仓库要求保留 implementation-unit commits 时，使用 rebase 后合入或 GitLab semi-linear history；仓库明确要求 squash 时遵循仓库规则。

## 工作树策略

使用 worktree 的条件：

- 多个 Agent 或会话并发。
- 当前工作区已有另一任务的未提交改动。
- 需要同时保留 `dev`、release、hotfix 或多个主题分支。
- 长时间任务不能阻塞主工作区。

命名建议：

```text
仓库：<agent-service-repo>
分支：feat/voice-kb
目录：../<agent-service-repo>-voice-kb
```

创建前确认目标目录不存在、分支未被其他 worktree 占用。移除前确认工作树干净、提交已合入且无进程继续使用：

```bash
git worktree list
git -C <worktree-path> status --short
git worktree remove <worktree-path>
git branch -d <topic-branch>
```

删除远端分支需单独确认：

```bash
git push origin --delete <topic-branch>
```

## 正常发布

无冻结或并行版本需求时，不创建 release 分支：

1. 确认 `dev` 已同步、工作区干净且验收通过。
2. 通过仓库规定的 MR/合入方式将 `dev` 合入 `master`。
3. 确认 `master` 的目标提交就是生产候选。
4. 更新版本与发布记录；具体步骤交给对应发布技能。
5. 创建带注释的版本 Tag 并推送。
6. 部署并验证生产环境。

不要仅凭本地分支名称判断已发布；以远端 `master`、Tag、流水线和实际部署提交共同确认。

## Release 分支

仅在以下场景创建：

- 发布冻结后 `dev` 仍需接收下一版本功能。
- 同时维护多个候选版本。
- 需要独立的 test/pre 稳定化窗口。

流程：

```bash
git fetch origin
git switch -c release/vX.Y.Z origin/dev
git push -u origin release/vX.Y.Z
```

release 分支只接受版本号、发布记录和发布阻断修复。修复提交不得只留在 release：

1. 验收 release。
2. 合入 `master` 并在生产提交上打 Tag。
3. 将 release 中不在 `dev` 的修复回流 `dev`。
4. 确认远端和流水线后再删除 release。

## 生产 Hotfix

从生产基线创建：

```bash
git fetch origin
git switch -c hotfix/vX.Y.Z origin/master
```

只包含解决生产问题所需的最小改动和验证。完成后：

1. 合入 `master`。
2. 在实际生产提交上打补丁版本 Tag。
3. 部署并验证。
4. 将 hotfix 修复合入 `dev`。
5. 若存在活跃 `release/*`，将同一修复合入对应 release。

优先保留同一修复提交的血缘。若目标分支差异过大必须 cherry-pick，记录来源提交并确认不会造成未来重复合入。

## 同步、回滚与异常

| 场景 | 处理 |
| --- | --- |
| 本地主题提交未推送，落后 `origin/dev` | rebase 到 `origin/dev` |
| 主题分支已共享 | 调用 `x-ai-git-sync` 判断 merge/rebase |
| `dev` 与远端分叉 | 停止直提，调用 `x-ai-git-sync` |
| ff-only 合入失败 | 重新诊断，不改成 force push |
| 共享分支提交有问题 | 追加修复或 `git revert` |
| merge/rebase 冲突 | 调用 `x-ai-git-sync`，可 abort 回原状 |
| 远端被 force push | 停止并核对协作者与 reflog，不盲目覆盖 |
| release 修复未回流 | 在删除 release 前补合入 `dev` |
| hotfix 只进了 `master` | 立即回流 `dev` 和活跃 release |

绝不使用 `--force` 覆盖共享历史。只有用户明确要求覆盖远端、已核对协作者且仓库允许时，才评估 `--force-with-lease`；这属于异常恢复，不是常规 Git Flow。

## 设计依据

- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)：短期分支、独立改动、评审、检查和合并后的分支清理。
- [GitLab Flow](https://docs.gitlab.com/topics/gitlab_flow/)：将功能分支、上游优先和环境/发布分支结合。
- [Git rebase](https://git-scm.com/docs/git-rebase)：将个人主题提交重放到最新上游。
- [Git push](https://git-scm.com/docs/git-push)：fast-forward、force 和 `--force-with-lease` 的底层规则。
- [Atlassian Gitflow Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow/)：经典 GitFlow 的发布分支模型及其在现代持续交付中的取舍。
