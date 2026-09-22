---
name: x-ai-docs-builder
description: AI 团队的全项目文档体系构建与治理技能。用于初始化或重构 docs、判断内容应落在 README/brainstorm/research/SDD/plan/guide/runbook/issue/solution 的哪一层、编写或更新完整文档、维护索引与交叉引用、审查断链孤儿文档和事实源冲突。用户提到项目文档结构、README 精简、文档归档、TODO/决策/评审发现整理、文档迁移或全仓库文档审查时使用；API、事件、页面、模型或数据契约以及 docs/sdd 场景还必须联用 x-ai-sdd。
---

# 项目文档体系构建

为整个项目选择正确的文档粒度、写出可维护的正文，并让入口、索引、事实来源和生命周期保持一致。

## 先确定约束

1. 找到 Git 根目录，读取适用的 `AGENTS.md`、仓库说明和项目共享记忆。
2. 检查根 `README.md`、`CHANGELOG.md`、`docs/`、代码入口、测试和现有文档链接。
3. 优先遵循用户明确要求和仓库既有规则。已批准或已提交的 design / plan、docs 索引中的明确约定也属于项目覆盖；本技能的目录模型只作为无明确约定时的默认值。
4. 只做审查或建议时保持只读；用户要求创建、整理或修复时才修改文件。
5. 工作区不干净时区分已有改动与本任务改动，不覆盖、移动或顺手提交无关文件。

## 选择工作模式

| 用户目标 | 模式 | 主要产物 |
| --- | --- | --- |
| “这个内容该放哪” | 路由 | 落点、理由、所需链接 |
| “写/更新某篇文档” | 写作 | 完整正文及必要索引 |
| “README 太细了” | 分层 | 精简入口，把细节下沉到 docs |
| “整理整个 docs” | 治理 | 现状盘点、目标结构、渐进迁移 |
| “检查文档问题” | 审计 | 断链、孤儿、状态与事实源报告 |
| “记录 API/事件/模型契约” | SDD 协作 | `x-ai-sdd` 规范正文及体系链接 |

若请求同时涉及多种模式，按“盘点 → 路由 → 写作 → 链接 → 审计”执行。

## 文档路由

先判断文档的读者、稳定性、权威性和下一步动作，再选择目录。完整决策树见 [document-routing.md](references/document-routing.md)。

| 内容 | 默认落点 | 关键边界 |
| --- | --- | --- |
| 项目定位、快速开始、最短使用路径 | 根 `README.md` | 只保留入口，不堆实现细节 |
| Agent / contributor 强制规则 | `AGENTS.md` | 长背景链接到 docs |
| 未收敛的想法与候选方案 | `docs/brainstorms/` | 不伪装成已决定方案 |
| 有证据的调研、POC、spike、benchmark | `docs/research/` | 记录来源、方法和结论边界 |
| 可验证行为契约与验收标准 | `docs/sdd/` | 必须联用 `x-ai-sdd` |
| 已选设计与实施步骤 | `docs/plans/` | 不替代 SDD，不把进度写成设计 |
| 稳定开发或使用方法 | `docs/guides/` | 面向重复使用 |
| 部署、运维、排障、恢复步骤 | `docs/runbooks/` | 写前置条件、验证和回滚 |
| TODO、开放决策、评审发现 | `docs/issues/` | 用 type/status 区分，不平铺多个目录 |
| 已验证的根因与解决经验 | `docs/solutions/` | 链接触发问题和最终改动 |
| 用户可见版本变化 | `CHANGELOG.md` 或发布文档 | 仅在项目有发布语义时维护 |

## 推荐结构

新项目或无既有约定的仓库使用 [information-architecture.md](references/information-architecture.md) 中的压缩结构：

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

目录按需创建，不生成空树。旧仓库先兼容、补导航，再按授权迁移。

## 执行流程

### 1. 盘点现状

- 列出根入口、docs 子目录、局部 README 和文档命名模式。
- 搜索文档对代码路径、API、配置、测试和其他文档的引用。
- 标记重复事实、孤立文件、遗留目录和状态字段。
- 对结构调整先给出现状树、目标树和映射表。

需要机器辅助时运行：

```bash
python3 <skill-dir>/scripts/audit_docs.py <repo-root>
python3 <skill-dir>/scripts/audit_docs.py <repo-root> --json
python3 <skill-dir>/scripts/audit_docs.py <repo-root> --strict
python3 <skill-dir>/scripts/audit_docs.py <repo-root> --baseline <audit.json> --strict
```

脚本只读。默认仅错误返回非零；`--strict` 也把告警视为失败。
项目明确长期保留历史目录或使用特殊导航入口时，在仓库根增加 `.docs-audit.json`，配置 `accepted_legacy_dirs`、`entrypoints` 或 `orphan_excludes`；格式见 [information-architecture.md](references/information-architecture.md)。
大型历史仓先用 `--json` 保存基线，再用 `--baseline` 只阻断新增问题；旧问题按批次清零后更新基线。

### 2. 建立事实来源

为每类事实选一个权威落点，其他文档只摘要并链接：

- 入口与快速开始 → 根 README
- 强制规则 → AGENTS
- 行为与验收 → SDD
- 设计决策与执行顺序 → plan
- 当前未闭环事项 → issue
- 稳定操作 → guide / runbook
- 根因与复用经验 → solution

不要把同一张状态表或同一套接口定义复制到多处。详细原则见 [lifecycle-and-cross-links.md](references/lifecycle-and-cross-links.md)。

### 3. 写正文

- 从 `assets/templates/` 选择最接近的骨架并按仓库约定裁剪，不机械填满所有章节。
- 开头说明目的、读者、范围和状态；正文先写结论，再写证据或步骤。
- 计划中的能力使用将来时或明确状态，不能写成已实现事实。
- 技术声明与代码、配置、测试、OpenAPI 或运行结果交叉核对。
- 路径、命令和标识符使用仓库真实值；不确定处记录为 issue，不猜测。
- 专业正文应完整，README 只保留完成首次操作所需内容并链接细节。

Python 服务的常见结构和核对点见 [python-project-profile.md](references/python-project-profile.md)。

### 4. 维护导航与生命周期

- 新增文档时更新最近的目录索引；重要专题再更新 `docs/README.md`。
- 根 README 只链接用户真正需要的一级入口。
- 文档通过引用演进，不因状态变化反复搬家。
- 新采用 `issues/` 统一模型且仓库没有其他格式时使用：
  - `type: decision | todo | review-finding`
  - `status: open | decided | planned | done | superseded`
- 仓库已明确采用 `todos/`、`open-issues/` 或其他元数据格式时继续沿用，除非用户批准迁移。
- 关闭 issue 时链接决定、提交、计划、规范或解决方案证据。
- 替代旧文档时保留稳定路径或明确 `superseded_by`，不要静默删除历史。

### 5. 审查与交付

使用 [review-checklists.md](references/review-checklists.md) 做与风险相称的检查：

1. 运行审计脚本和仓库既有文档校验。
2. 检查入口、索引、反向链接和相对路径。
3. 对照代码验证关键事实，对照 SDD 验证行为声明。
4. 查看 Git diff，确保没有改动计划外文件或混入用户已有改动。
5. 按仓库提交规范提交；只要求建议或审查时不创建提交。

## SDD 协作规则

以下任一情况出现时，同时使用 `x-ai-sdd`：

- 新建、修改或审查 `docs/sdd/`。
- 定义 API、事件、页面、模型、数据格式、状态机或错误语义。
- 用户要求 specification、contract、验收矩阵、R-ID 或规范驱动开发。

由 `x-ai-sdd` 决定规范结构、状态和追踪要求；本技能负责：

- 判断规范在项目文档地图中的位置。
- 链接上游 research / brainstorm 和下游 plan / guide / issue。
- 避免 README、guide 和 SDD 互相复制契约正文。

先区分“API 响应”实际指 Python SDK 返回模型、HTTP response envelope 还是事件/流协议；没有证据时不要把模块契约上升为项目统一规范。只搬迁已有契约文本时校验链接与一致性，不推进 SDD 生命周期；契约缺失或语义变化时才修改 SDD 和验收。

若 `x-ai-sdd` 不可用，遵循仓库现有 SDD 约定并明确说明缺失，不自行发明一套冲突规范。

## 兼容与迁移

在没有项目覆盖时，把这些目录识别为历史兼容形式但不自动搬迁：

- `todos/` → `issues/` + `type: todo`
- `open-issues/` → `issues/` + `type: decision`
- `reviews/`、`residual-review-findings/` → `issues/` + `type: review-finding`
- `poc/`、`spikes/` → `research/`

兼容可以采用长期保留、索引别名、旧路径存根或 `superseded_by`，选择标准见 [information-architecture.md](references/information-architecture.md)。大规模整理必须先输出旧路径、目标路径、链接影响和迁移顺序。删除、覆盖、批量移动和修改外部系统需要用户明确授权。

## 资源索引

- [information-architecture.md](references/information-architecture.md)：目录职责、最小结构和兼容映射。
- [document-routing.md](references/document-routing.md)：分类决策树和常见请求路由。
- [lifecycle-and-cross-links.md](references/lifecycle-and-cross-links.md)：状态、引用演进和事实来源。
- [review-checklists.md](references/review-checklists.md)：单篇与全仓库审查清单。
- [python-project-profile.md](references/python-project-profile.md)：Python 服务文档画像。
- `assets/templates/`：可复制并裁剪的八类 Markdown 骨架。
- `scripts/audit_docs.py`：只读文档结构审计。
