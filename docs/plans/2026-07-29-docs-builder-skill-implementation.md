# 项目文档体系构建技能实施计划

1. 使用 `skill-creator/scripts/init_skill.py` 初始化 `x-ai-docs-builder`，创建 `scripts/`、`references/`、`assets/` 和 `agents/openai.yaml`。
2. 编写 `SKILL.md`，覆盖规则发现、仓库盘点、文档路由、写作、索引维护、审计与渐进迁移，并声明 SDD 场景联用 `x-ai-sdd`。
3. 编写信息架构、文档路由、生命周期与交叉引用、审查清单、Python 项目画像五份参考资料。
4. 编写 docs 索引、头脑风暴、调研、计划、指南、运行手册、问题和解决方案八类可复制模板。
5. 实现只读 `scripts/audit_docs.py`，检查断链、孤儿、索引、issue 元数据、重复 ID 和历史目录，并支持文本与 JSON 输出。
6. 在 `x-ai-sdd` 中增加反向职责边界，并修正生命周期清单写死旧归档路径的冲突。
7. 更新仓库 README 技能清单、Claude 批量安装命令、Codex 安装示例和 docs 索引。
8. 使用临时仓库验证审计脚本的干净、故障、项目覆盖和历史基线场景，运行 `quick_validate.py`。
9. 对三个现有 Python 仓库执行只读前向测试，确认技能能尊重既有规则、正确路由文档并在契约场景转交 `x-ai-sdd`。
10. 检查最终 diff、脚本权限和提交消息，创建只包含本技能实现的本地提交。
