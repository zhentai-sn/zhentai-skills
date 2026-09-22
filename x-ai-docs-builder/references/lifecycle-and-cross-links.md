# 生命周期、交叉引用与事实来源

## 引用式演进

文档阶段变化时不反复移动同一文件，而是创建承担新角色的文档并引用前序证据：

```text
brainstorm → research → SDD → design/plan → guide/runbook
                    ↘ issue ↗          ↘ solution
```

例如 research 得出选型结论后，SDD 引用结论并定义契约；plan 引用 SDD 安排实现；guide 只说明稳定用法。这样历史推理、当前契约和操作说明可以分别演进。

## 最小元数据

不要强迫所有仓库采用 YAML frontmatter。仓库已有格式时沿用。需要显式状态且无既有规则时，可用：

```yaml
---
id: DOC-001
title: 示例标题
status: active
owners:
  - team-name
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - ../research/example.md
superseded_by:
---
```

只填写真正维护的字段。自动化依赖某字段前，先在 `docs/README.md` 中声明约定。

## issue 元数据

新采用 `docs/issues/` 且仓库没有既有格式时，文档至少包含：

```yaml
---
id: ISSUE-001
title: 待处理事项
type: decision
status: open
---
```

合法值：

- `type`: `decision`、`todo`、`review-finding`
- `status`: `open`、`decided`、`planned`、`done`、`superseded`

建议状态转换：

```text
open → decided → planned → done
  └────────────────────→ superseded
```

并非每个类型都必须经过所有状态。关闭时增加 `resolution`、`resolved_by` 或正文证据链接。
决策被否决时仍可使用 `status: decided`，并以 `resolution: rejected` 保留结果；不要把 rejected 硬映射成 done 或丢失原语义。

仓库已有 TODO/decision/review 目录或非 YAML 元数据时，以项目约定为准。不要为了满足默认模板而重写历史格式；先在 docs 索引或项目设计中声明统一规则，再决定是否迁移。

## 单一事实来源

| 事实 | 权威位置 | 其他位置怎样引用 |
| --- | --- | --- |
| 项目用途与最短启动 | 根 README | 索引只给一句摘要 |
| 强制开发规则 | AGENTS | plan 指向规则，不复制 |
| 行为契约与验收 | SDD | README/guide 给使用级摘要 |
| 设计选择 | design/plan | SDD 不写实现细节 |
| 当前问题状态 | issue | 索引聚合状态 |
| 稳定操作方法 | guide/runbook | solution 链接最终方法 |
| 根因与修复证据 | solution | issue 关闭时链接 |

发现两处内容都自称权威时：

1. 根据仓库规则和读者选择唯一来源。
2. 更新权威正文。
3. 把另一处改为短摘要和链接。
4. 若无法决定，创建 `type: decision` 的 issue。

## 链接规则

- 仓库内 Markdown 优先使用相对链接。
- 链接到文件而不是易变化的行号；必要时链接稳定标题锚点。
- 上游文档链接直接来源，下游文档链接明确“落实于”或“替代于”。
- 重命名前搜索代码、CI、站点配置、issue 和外部文档中的路径。
- 文档被替代时保留简短说明和 `superseded_by`，直到确认旧链接无消费者。

## 索引状态

索引只显示对读者有用的状态，不维护另一套进度：

```markdown
| 文档 | 类型 | 状态 | 说明 |
| --- | --- | --- | --- |
| [响应契约](issues/api-response-contract.md) | decision | open | 待统一业务码与错误体 |
```

状态必须来自目标文档元数据或明确正文，不能在索引中独立更新。

## 文档 ID

- 只有需要跨文档追踪或自动化时才引入 ID。
- ID 在仓库内唯一，重命名文件不改变 ID。
- SDD 的 R-ID、决策 ID 和 issue ID 使用不同前缀。
- 不从目录序号自动推导永久 ID。
