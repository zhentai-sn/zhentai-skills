# 中间件存储治理技能实施计划

1. 使用 `skill-creator/scripts/init_skill.py` 初始化 `x-ai-middleware-storage`，创建 `references/` 和 `agents/openai.yaml`。
2. 编写精简的 `SKILL.md`，覆盖触发范围、通用诊断流程、增长率估算、安全确认门禁、变更执行与验证。
3. 编写 `references/langfuse-clickhouse-minio.md`，沉淀本次 Langfuse、ClickHouse、MinIO、PostgreSQL、Redis 的真实操作配方和跨 Shell 踩坑。
4. 更新 README 技能清单及 Claude/Codex 安装示例。
5. 运行 `quick_validate.py`、YAML/命令安全检查和仓库 diff 检查，修复发现的问题。
6. 将仓库源目录同步安装到 `C:\Users\<user>\.agents\skills\x-ai-middleware-storage` 并比对内容。
7. 提交实现改动，推送 `master` 到远端，确认工作树干净且远端包含设计与实现提交。
