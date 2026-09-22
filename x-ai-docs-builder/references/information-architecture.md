# 项目信息架构

## 默认结构

只有在仓库没有更明确约定时，才采用以下结构。目录按需创建：

```text
README.md
AGENTS.md
CHANGELOG.md
docs/
├── README.md
├── brainstorms/
├── research/
├── sdd/
├── plans/
├── guides/
├── runbooks/
├── issues/
└── solutions/
```

最小项目通常只需要根 README、AGENTS 和 `docs/README.md`；其余目录在第一篇对应文档出现时创建。

## 根文件职责

### `README.md`

回答“这是什么、为什么用、怎样完成第一次成功操作、接下来去哪看”。推荐顺序：

1. 一句话定位。
2. 核心能力或适用场景。
3. 最短安装和运行路径。
4. 最小配置。
5. 文档地图。
6. 开发与贡献入口。

架构细节、完整配置表、所有接口、排障长文和历史讨论应下沉到 docs。

### `AGENTS.md`

只保存执行任务时必须知道的规则：仓库定位、关键命令、不可违反的架构约束、测试门禁、提交规范和事实来源链接。不要复制完整 SDD 或 runbook。

### `CHANGELOG.md`

只有项目对外发布版本或需要面向使用者追踪变化时维护。内部实验仓可以省略；迁移细节较长时另建发布或迁移文档并从 changelog 链接。

## docs 目录职责

| 目录 | 核心问题 | 典型状态 | 不应承载 |
| --- | --- | --- | --- |
| `brainstorms/` | 有哪些可能性 | exploring / converged | 已承诺契约 |
| `research/` | 证据说明什么 | active / concluded / superseded | 无证据的偏好 |
| `sdd/` | 系统必须怎样表现 | draft / ready / implemented / accepted | 操作教程 |
| `plans/` | 选定方案怎样落地 | proposed / approved / completed | 永久契约 |
| `guides/` | 怎样稳定地使用或开发 | current / deprecated | 临时排障流水 |
| `runbooks/` | 怎样操作环境和恢复 | current / deprecated | 产品需求 |
| `issues/` | 还有什么未闭环 | open / decided / planned / done / superseded | 长篇最终知识 |
| `solutions/` | 什么根因与方案已验证 | verified / superseded | 未验证猜测 |

## 索引层级

- 根 README：只列高价值入口。
- `docs/README.md`：列目录职责、事实来源、活跃专题和重要状态。
- 专题目录 README：目录有多篇文档或明确子主题时创建。
- 单篇文档：链接直接上游和直接下游，不维护全局清单。

索引是导航，不复制正文。一个目录只有一篇文档时通常无需局部 README。

## 历史兼容

| 发现的路径 | 默认解释 | 建议 |
| --- | --- | --- |
| `docs/todos/` | 待办事项 | 新内容写入 `issues/`，旧内容先保留链接 |
| `docs/open-issues/` | 待决策事项 | 映射为 `type: decision` |
| `docs/reviews/` | 评审记录或发现 | 发现映射为 `review-finding`；完整评审报告可保留专题 |
| `docs/residual-review-findings/` | 未闭环评审发现 | 映射为 `type: review-finding` |
| `docs/poc/`、`docs/spikes/` | 实验与可行性验证 | 报告归 `research/` 语义；代码、数据和二进制资产按工程用途保留或另行治理 |
| `docs/design/`、`docs/designs/` | 设计文档 | 已承载稳定跨专题设计或被广泛引用时保留；否则可与 `plans/` 的 design 命名统一 |
| `docs/api/` | API 参考或教程 | 契约归 SDD，使用方法归 guides |
| `docs/prd/` | 产品输入或需求原稿 | 作为 SDD 输入保留；差距进 research/issues，实施进 plans |

不要因为默认结构不同就立即改名。仓库 `AGENTS.md`、docs 索引或已批准/已提交的 design / plan 已明确采用某个路径时，该路径是项目覆盖，不再把它当作待迁移目录。先确认外部链接、CI、站点生成器和团队习惯，再决定是否迁移。

## 兼容形式选择

| 条件 | 兼容形式 |
| --- | --- |
| 路径仍被代码、AGENTS、CI 或大量外部文档引用 | 长期保留，在新索引中解释其语义 |
| 新旧目录需要并行一段时间 | 新索引同时链接，旧目录 README 指向新入口 |
| 可以保留单文件但正文已迁移 | 旧路径存根 + `superseded_by` |
| 所有消费者可在同一变更中更新 | 经批准后移动，并批量修正链接 |

审计器默认提示通用历史目录。项目明确接受这些路径或有额外导航入口时，在仓库根增加：

```json
{
  "accepted_legacy_dirs": [
    "todos",
    "residual-review-findings"
  ],
  "entrypoints": [
    "docs/TODO.md"
  ],
  "orphan_excludes": [
    "docs/generated/*.md"
  ]
}
```

- `accepted_legacy_dirs`：不再提示对应 `docs/<name>/`。
- `entrypoints`：作为根 README、`docs/README.md` 之外的合法导航起点。
- `orphan_excludes`：只免除匹配文档的孤儿告警，不跳过断链检查。

配置只用于表达已确认的项目差异，不能用来隐藏尚未判断的大量问题。

大型历史仓不要一次把数百条告警加入 `orphan_excludes`。先保存完整 JSON 审计结果作为基线，再用 `--baseline <file> --strict` 阻断新增问题；修完一批后重新生成基线，直到可以无基线 strict。

## 可选扩展

满足明确需求时才增加：

- `docs/releases/`：发布说明、升级指南和兼容矩阵。
- `docs/security/`：威胁模型、安全响应与披露策略。
- `docs/adr/`：仓库已采用 ADR 且不希望设计记录放入 plans。
- `docs/reference/`：大量自动生成或稳定查阅型参考资料。

新增目录前说明它与现有目录的不可替代边界。
