# 项目文档体系构建技能设计

## 目标与边界

新增 `x-ai-docs-builder`，为AI 团队提供覆盖整个项目生命周期的文档规划、编写、审查与治理能力。它负责从仓库入口到专题文档的整体信息架构，既能为新项目建立最小可用文档体系，也能在不破坏既有约定的前提下整理历史仓库。

该技能负责：

- 识别仓库现有规则、文档类型和事实来源。
- 判断内容应落在 README、调研、规范、计划、指南、运行手册、问题或复盘中的哪一层。
- 编写或更新完整文档，而不只生成目录建议。
- 维护索引、交叉引用、状态和来源追踪。
- 审查断链、孤儿文档、重复事实、失效路径和不一致状态。
- 为旧目录提供兼容映射，并按需规划渐进迁移。

该技能不取代具体领域的事实来源，也不把所有文档都改写成同一模板。仓库内 `AGENTS.md`、用户明确要求和既有项目约定优先。

## 与 `x-ai-sdd` 的分工

`x-ai-docs-builder` 是项目级编排者，处理所有文档类型、目录结构和跨文档关系；`x-ai-sdd` 是契约级专家，只负责 `docs/sdd/` 中可验证、可追踪的行为规范。

| 场景 | 主技能 | 协作方式 |
| --- | --- | --- |
| README、文档导航、指南、运行手册、问题台账、复盘 | `x-ai-docs-builder` | 独立完成 |
| 新功能应写调研、设计还是计划 | `x-ai-docs-builder` | 先分类，再写作 |
| API、事件、页面、模型或数据契约 | `x-ai-docs-builder` + `x-ai-sdd` | 前者负责体系与链接，后者负责规范正文 |
| 只要求编写或审查 SDD | `x-ai-sdd` | 遵循现有 `docs/sdd/` 结构 |
| 全仓库文档重构 | `x-ai-docs-builder` | 识别并保留 SDD 的规范边界 |

两者发生冲突时，仓库规则优先；对于正式契约内容，以 `x-ai-sdd` 的约束为准。

## 推荐信息架构

新项目默认采用压缩后的核心结构，目录按需创建，不生成空目录：

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

各层职责如下：

- 根 `README.md`：项目定位、快速开始、最短使用路径和文档入口。
- `AGENTS.md`：Agent 与 contributor 必须遵守的仓库约束，不承载长篇背景。
- `CHANGELOG.md`：面向使用者的版本变化；仅在项目有发布语义时保留。
- `docs/README.md`：文档地图、事实来源说明、活跃专题和状态索引。
- `brainstorms/`：尚未收敛的问题空间、方案候选和探索记录。
- `research/`：有证据的调研、POC、spike、基准与外部系统分析。
- `sdd/`：行为契约、需求、验收标准和追踪关系。
- `plans/`：已选方案的设计记录与实施计划。
- `guides/`：面向开发者或使用者的稳定操作说明，也承载 API 使用指南。
- `runbooks/`：部署、运维、排障、恢复等环境相关操作；没有运维场景时可不创建。
- `issues/`：尚需决策或处理的事项，统一 TODO、开放决策和评审发现。
- `solutions/`：已验证的问题解决记录、根因和可复用经验。

发布说明、迁移说明等低频类型按项目需要增加，不作为所有仓库的默认目录。

## `issues/` 统一模型

不再默认并列维护 `todos/`、`open-issues/`、`reviews/` 和 `residual-review-findings/`。新文档统一进入 `docs/issues/`，通过元数据区分：

- `type: decision | todo | review-finding`
- `status: open | decided | planned | done | superseded`

状态变化只更新元数据和索引，不移动文件，以保持链接稳定。历史目录作为兼容别名识别：

| 历史目录 | 统一语义 |
| --- | --- |
| `todos/` | `issues/` + `type: todo` |
| `open-issues/` | `issues/` + `type: decision` |
| `reviews/`、`residual-review-findings/` | `issues/` + `type: review-finding` |
| `poc/`、`spikes/` | `research/` |

技能不会仅因发现旧目录就自动批量移动文件；先生成映射与迁移建议，获得授权后再实施。

## 文档演进与事实来源

文档通过引用晋级，不通过搬家晋级：

```text
brainstorm → research → SDD → design/plan → guide/runbook
                    ↘ issue ↗          ↘ solution
```

每篇文档应明确自身角色，并链接上游依据与下游产物。后续文档引用前序结论，而不是复制整段内容。关键事实只选择一个权威落点：

- 用户可见入口与快速开始：根 README。
- 必须遵守的仓库规则：AGENTS。
- 行为契约和验收标准：SDD。
- 设计决策与执行顺序：plan。
- 当前未闭环事项：issue。
- 稳定使用或运维方法：guide / runbook。
- 已验证根因与修复经验：solution。

索引负责聚合链接和状态，不重新讲述正文。

## 工作流

1. 识别 Git 根、仓库规则、共享项目记忆和既有文档结构。
2. 盘点文档入口、目录、命名、索引、状态字段和代码引用。
3. 根据读者、时效、权威性和下一步动作判断文档类型。
4. 选择新建、更新、拆分、合并、建立索引或兼容映射；先报告会改变结构的判断。
5. 对契约类内容同时使用 `x-ai-sdd`，其余类型使用对应模板与检查表。
6. 更新必要的入口、索引和交叉引用，避免只新增孤立文件。
7. 运行只读文档审计，检查断链、孤儿、缺失索引、遗留目录和状态问题。
8. 复核代码路径与事实来源，按仓库提交规范落地。

## 技能结构

```text
x-ai-docs-builder/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── information-architecture.md
│   ├── document-routing.md
│   ├── lifecycle-and-cross-links.md
│   ├── review-checklists.md
│   └── python-project-profile.md
├── assets/
│   └── templates/
│       ├── docs-index.md
│       ├── brainstorm.md
│       ├── research.md
│       ├── plan.md
│       ├── guide.md
│       ├── runbook.md
│       ├── issue.md
│       └── solution.md
└── scripts/
    └── audit_docs.py
```

`SKILL.md` 保持精简，只承载触发范围、主流程、路由入口和安全边界。详细规则放在单层 `references/` 中；可直接复制并按项目裁剪的文档骨架放在 `assets/templates/` 中。

## 审计机制

`audit_docs.py` 默认只读，至少检查：

- Markdown 相对链接指向不存在的文件或目录。
- `docs/` 存在但缺少 `docs/README.md`。
- 未从根 README、docs 索引或其他文档到达的孤儿文档。
- 核心专题目录含多篇文档但没有局部 README 索引。
- `issues/` 文档缺少或使用非法的 `type` / `status`。
- 重复文档 ID。
- 已知历史目录仍在使用。

输出同时支持人类可读文本和 JSON。错误与建议分级，遗留目录只告警，不阻断历史仓库。

## 安全与迁移策略

- 先读后写，不凭目录名推断内容。
- 不自动删除、覆盖或批量移动历史文档。
- 不把计划中的行为写成已实现事实；状态必须有证据。
- 不复制外部文档的大段正文，优先记录来源、结论和适用范围。
- 涉及大量重命名时先给出映射表，并单独实施与提交。
- 旧仓库优先兼容和建立导航；新仓库才默认采用推荐结构。
- 文档改动需要和相关代码、配置、测试或 API 定义交叉核对。

## 验证标准

- 技能目录通过 `quick_validate.py`。
- `agents/openai.yaml` 满足展示字段规范，默认提示词显式引用 `$x-ai-docs-builder`。
- 审计脚本在干净与故障临时样例上分别得到预期结果。
- 对至少三个现有 Python 仓库进行只读前向测试，能尊重不同仓库结构并给出可执行落点。
- 对 SDD 场景能明确调用 `x-ai-sdd`，不重复或削弱契约约束。
- README 技能清单和本地安装示例包含 `x-ai-docs-builder`。
- 设计与实现分别提交到本地，提交信息遵循仓库规范且不包含模型署名。
