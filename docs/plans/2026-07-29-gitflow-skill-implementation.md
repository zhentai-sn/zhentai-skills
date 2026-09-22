# 现代 Git Flow 技能实施计划

1. 使用 `skill-creator/scripts/init_skill.py` 初始化 `x-ai-gitflow`，创建 `scripts/`、`references/` 和 `agents/openai.yaml`。
2. 编写 `SKILL.md`，覆盖仓库规则优先级、状态诊断、`dev` 直提边界、主题分支与 worktree 选择、合入、发布和热修流程。
3. 编写 `references/policy.md`，沉淀分支矩阵、命名、MR 门槛、发布回流和异常处理配方。
4. 编写只读 `scripts/gitflow-status.sh`，输出仓库、工作区、分支、上游和领先/落后状态。
5. 更新 README 技能清单及 Claude/Codex 安装示例。
6. 在临时 Git 仓库覆盖脚本的干净、脏工作区、有上游和无上游场景，并运行 `quick_validate.py`。
7. 将仓库源目录同步到本机技能入口，检查 diff 与提交信息，提交实现并推送 `master`。
