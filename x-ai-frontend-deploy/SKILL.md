---
name: x-ai-frontend-deploy
description: AI 团队 业务管理端前端的 GitLab 流水线部署流程。用户提到部署或发布 <admin-frontend-repo>、触发前端流水线、选择部署分支/环境/租户、把管理端发到 development/test/preview，或要求打开 GitLab New pipeline 页面代操作时使用。仅允许代操作非生产环境，点击 New pipeline 前必须按分支、环境、租户二次确认；production 必须由用户纯手工操作，Agent 禁止打开页面代填或触发。
---

# 业务管理端前端部署

通过 GitLab 的 **Run new pipeline** 页面部署 `<admin-frontend-repo>`。本技能只负责创建流水线并报告创建结果；除非用户另行要求，不持续监控、重试、取消或操作流水线中的 Job。

## 固定目标

- 项目：`<platform>/<business-repo>/<admin-frontend-repo>`
- 新建流水线：<https://<gitlab-host>/<group>/<admin-frontend-repo>/-/pipelines/new>
- 输入来源：仓库根目录 `.gitlab-ci.yml` 的 `spec.inputs`

## 安全门禁

### 禁止代操作生产环境

只要目标环境是 `production`，立即停止所有浏览器操作：

- 不打开 GitLab 部署页面。
- 不选择分支、环境或租户。
- 不点击 **New pipeline**。
- 不通过 API、CLI 或其他自动化方式绕过限制。

只向用户提供上面的固定入口和待手工选择的分支、`ENV=production`、`BUSINESS=<租户>`，明确说明生产环境必须由用户全程手工操作。

### 非生产环境必须二次确认

`development`、`test`、`preview` 可以代操作，但 **New pipeline** 是产生外部状态的最终动作。填好页面后，必须先向用户展示：

```text
项目：<platform>/<business-repo>/<admin-frontend-repo>
分支：<branch-or-tag>
环境：<development|test|preview>
租户：<business>
动作：创建一条新的 GitLab 流水线
```

等待用户针对这组完整参数明确回复“确认触发”“开始部署”等同意语句后，才能点击一次 **New pipeline**。早先对技能规则的笼统同意不算本次部署确认。参数发生任何变化后，旧确认立即失效，必须重新展示摘要并确认。

## 输入值

### ENV（构建环境）

| 值 | 含义 | Agent 是否可操作 |
| --- | --- | --- |
| `development` | 开发环境 | 可以，需二次确认 |
| `test` | 测试环境 | 可以，需二次确认 |
| `preview` | 预发布环境 | 可以，需二次确认 |
| `production` | 生产环境 | 禁止，必须纯手工 |

不要使用空值让分支规则隐式决定环境；部署前必须取得明确的 `ENV`。

### BUSINESS（租户/业务方）

多租户部署时 `BUSINESS` 是租户代码，页面下拉里每个值对应一个具体业务方（`default` 为平台本身）。**具体的租户代码与业务方对照属于客户信息，请按自己环境的 CI 配置维护，不要写进公开文档。**

取值以**当前页面选项**和**当前目标分支的 `.gitlab-ci.yml`** 为准，不猜测新值。如果用户只给中文业务方名称，按自己维护的对照表映射后，在确认摘要中同时写出中文名和代码，让人能核对。

### BUSINESS_PIPELINES

单租户部署时必须选择非空 `BUSINESS`，此时 `BUSINESS_PIPELINES` 不生效。保持页面默认值，不修改、不清空，也不要把它误当作租户字段。

## 操作流程

### 1. 收齐并校验参数

必须明确得到三项：

1. 精确分支名或 tag。
2. 非生产环境：`development`、`test` 或 `preview`。
3. 租户 `BUSINESS`。

缺少任何一项就只询问缺失项，不根据当前本地分支、截图示例或历史部署记录擅自推断。用户请求 `production` 时执行“禁止代操作生产环境”，不进入后续步骤。

### 2. 打开目标页面

使用可复用现有登录态的浏览器控制能力打开固定入口。若未登录，停下并请用户在该浏览器中登录 GitLab，用户说明已登录后再继续。不得读取 Cookie、密码、浏览器配置或会话存储。

确认页面所属项目正是 `<platform> / <business-repo> / <admin-frontend-repo>`。项目不一致时停止，不在其他项目创建流水线。

### 3. 填写页面

按顺序操作：

1. 在 **Run for branch name or tag** 选择精确分支或 tag；找不到时停止并报告，不改选相近名称。
2. 在 **Inputs** 将 `ENV` 设为目标非生产环境。
3. 将 `BUSINESS` 设为目标租户。
4. 保持 `BUSINESS_PIPELINES` 默认值。
5. 不填写下方自由格式的 **Variables**。

### 4. 暂停并二次确认

读取页面当前可见值，与用户要求逐项核对。展示“项目、分支、环境、租户、动作”摘要，然后暂停等待明确确认。此时不得点击 **New pipeline**。

### 5. 创建一次流水线

收到有效确认后，再次核对页面当前值没有变化，然后只点击一次 **New pipeline**。点击后等待 GitLab 跳转或显示创建结果，不因页面响应慢而重复点击。

### 6. 回报结果

成功创建后返回：

- 流水线 ID 与链接（页面可见时）。
- 分支、环境、租户。
- 当前状态，如 `created`、`pending`、`running`。

使用“流水线已创建”，不要把它表述为“部署成功”。只有流水线完成且部署 Job 成功后，才能说部署成功。

## 异常处理

- 分支或输入选项不存在：停止并请用户核对，不选择近似项。
- 权限不足或登录失效：请用户登录或申请权限，不尝试获取凭据。
- 创建后页面结果不明确：先检查是否已经产生流水线，不能直接重试。
- 流水线失败：报告失败 Job 和页面信息；重试、取消、手动运行 Job 都需要新的明确授权。
- 用户临时把环境改成 `production`：立即停止浏览器操作，转为纯手工提示。

## 典型触发语句

- “把 `feature/scale-matrix-table` 部署到 test 的租户。”
- “帮我触发 业务管理端前端的预发流水线。”
- “打开前端 GitLab，选择分支、环境和租户后部署。”

