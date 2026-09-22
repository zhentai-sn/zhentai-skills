# zhentai-skills

一个人在真实项目里攒出来的 Claude Code / Agent Skills，统一以 `x-ai-` 前缀命名。18 个技能，覆盖文档方法论、Git 工作流、发布部署、环境运维、排障取数五类。

> **这是脱敏后的公开版本。** 原始仓库面向内部环境，公开前已把内网 IP、主机名、内部域名、仓库地址、业务系统标识统一替换为 `<占位符>`（如 `<gitlab-host>`、`<api-test-host>`、`<db-ip>`）。照着用时把占位符换成你自己的环境即可；技能里的方法、顺序与踩坑记录保持原样。

## 这个仓是什么

**每个技能是一件「做过、踩过坑、不想再从头想一遍」的事的操作契约。**

| 是 | 不是 |
| --- | --- |
| 从真实事故与重复劳动里提炼的步骤、判据和踩坑清单 | 从文档抄来的教程或最佳实践汇编 |
| 给 agent 读的约束：什么顺序做、什么必须先确认、什么禁止 | 给人读的科普 |
| 有明确触发条件（`description` 决定何时被自动选中） | 需要人记住并手动翻阅的 wiki |

写技能的判据只有一条：**同一类活干到第二次、并且第二次还在重新试错**，就该沉淀。只做过一次的不写，做两次都很顺的也不写。

## 五个领域

| 领域 | 技能 | 解决的共同问题 |
| --- | --- | --- |
| **文档与方法论** | `x-ai-sdd`、`x-ai-docs-builder`、`x-ai-feishu-doc` | 写什么、写在哪、按什么结构写 |
| **Git 工作流** | `x-ai-gitflow`、`x-ai-git-sync` | 分支怎么开怎么合、分叉了怎么收 |
| **发布与部署** | `x-ai-ci-deploy`、`x-ai-server-deploy`、`x-ai-frontend-deploy`、`x-ai-pkg-publish`、`x-ai-backend-lib-release`、`x-ai-webhook-message` | 代码怎么从本地走到环境上，失败了怎么知道 |
| **环境与运维** | `x-ai-private-env-ops`、`x-ai-nginx-domain`、`x-ai-middleware-storage`、`x-ai-ssh-remote` | 机器怎么连、域名证书怎么挂、磁盘怎么不被撑爆 |
| **排障与取数** | `x-ai-log-cls-trace`、`x-ai-backend-mysql`、`x-ai-apifox-mcp` | 出问题怎么定位，要数据怎么安全地拿 |

越往下越贴具体环境，也越需要按自己的情况改写；最上面两类基本可以直接拿走用。

## 怎么生长的

**不是规划出来的，是遇到一次、解决一次、沉淀一次。**

| 时间 | 新增 | 当时在做什么 |
| --- | --- | --- |
| 2026-06-27 | 5 个 | 第一批，把已经反复口头解释过的事一次性落成文件 |
| 2026-06 ~ 07 | 11 个 | 密集期：每接一类新活就补一个 |
| 2026-08 起 | 2 个 | 趋缓，只在遇到真正的新领域时新增 |

生长出三层成熟度，从目录形态就能看出来：

- **只有 `SKILL.md`**（6 个）—— 一次性沉淀，之后没再遇到新情况
- **带 `scripts/` 或 `agents/`**（6 个）—— 步骤稳定到可以固化成可执行文件
- **带 `references/`**（6 个）—— 反复用过，细节多到必须分文件，主文件只留判断
- **另有 3 个在 `docs/plans/` 留了设计记录** —— `docs-builder`、`gitflow`、`middleware-storage`，改动大到值得先写设计再动手

规模差距很直观：最大的 `x-ai-docs-builder` 669 行 16 个文件，最小的 `x-ai-ssh-remote` 113 行。**行数不代表重要性，代表这件事被踩过多少次坑。**

## 未来会怎么发展

按现状能看见的三个方向，不画大饼：

- **补齐 references** —— 单文件技能里，`ci-deploy`（326 行）和 `webhook-message`（267 行）已经长到该拆了，主文件塞太多细节会稀释判断
- **加机械校验** —— 目前 `frontmatter.name` 与目录名是否一致、软链是否登记，全靠人工核对。该有个脚本在提交前跑
- **收敛而不是无限增加** —— 技能多了以后，`description` 之间会互相干扰、导致选错。到 25 个左右应该开始合并同类项，而不是继续加

有一类明确**不会**加：一次性的、或者强绑定某个具体业务表结构的操作。那种写下来也不会有第二次使用，只会变成噪音。

同样的理由，内部版本里有两个技能没有放进来——它们整篇都在讲某套具体业务表怎么补数据、某个具体后台怎么导题目，把业务细节抽掉之后只剩空壳，留着反而误导。

## 技能清单（按名称）

| Skill | 用途 |
| --- | --- |
| `x-ai-apifox-mcp` | 给 Claude Code 接入 Apifox MCP，并读取项目接口(OpenAPI) —— 配 server、找工具、解析超长 OAS、按 path 前缀统计模块接口数 |
| `x-ai-backend-lib-release` | Java/Maven 公共包(SNAPSHOT)改动发布到环境全链路 —— IDE mvn deploy 到 Nexus + 消费方 CI 重建 + k8s 换镜像 tag，含「SNAPSHOT 构建期解析」心智模型与踩坑清单 |
| `x-ai-ci-deploy` | Python 业务服务接入公司 GitLab 通用 CI 模板 + Docker 镜像构建 + 单机部署三件套 |
| `x-ai-docs-builder` | 全项目文档体系构建与治理——文档路由、完整写作、索引与交叉引用、渐进迁移、结构审计，并与 x-ai-sdd 分工协作 |
| `x-ai-feishu-doc` | 在飞书上与用户协作整理长文档（调研/方案/汇报）—— 协作铁律与安全改稿、背景→难点→方案→验收的主线意识、一问一表与同级可比、要点改写成可执行步骤、名词解释与编号规范，附 DocxXML 实操坑 |
| `x-ai-frontend-deploy` | 通过 GitLab 安全触发 业务管理端前端非生产环境部署；提交前二次确认，生产环境禁止代操作 |
| `x-ai-gitflow` | 现代 Git Flow——dev 直提边界、短期主题分支、并发 worktree、MR/ff-only 合入、release 与 hotfix 回流 |
| `x-ai-git-sync` | 处理本地分支与远端的分叉(diverged)——fetch 看清两边、估冲突、决策 rebase/merge、安全回滚与推送 |
| `x-ai-log-cls-trace` | 腾讯云 CLS 日志按 TraceID 全链路排障 |
| `x-ai-middleware-storage` | Docker/Compose 中间件存储治理——容量盘点、每日增长率、日志/数据保留策略与确认后的安全清理；首版覆盖 Langfuse + ClickHouse + MinIO |
| `x-ai-nginx-domain` | 给服务器服务挂域名——Nginx 反向代理、DNSPod A/CNAME 解析、HTTPS 证书与上游路由端到端验收 |
| `x-ai-pkg-publish` | Python 公共包发布流程（预发布 Alpha/Beta/RC + 正式发布门禁） |
| `x-ai-sdd` | SDD（规范文档驱动开发）方法论与模板 |
| `x-ai-server-deploy` | Python 服务部署到服务器并验证（拉镜像 → compose 起容器 → 健康确认） |
| `x-ai-private-env-ops` | 经堡垒机操作私有化客户环境服务器 —— <dmz-nginx> 目标机运维、SSL 证书更换；Node.js ssh2 跨平台(Windows/WSL/Mac)、DPAPI/Keychain 存凭据、含环境拓扑图与写操作确认门禁 |
| `x-ai-ssh-remote` | 非交互 SSH 登录服务器跑命令（无 sshpass 时走 paramiko）+ 密码到密钥登录的安全迁移 |
| `x-ai-webhook-message` | 给 GitLab CI/CD 流水线接 webhook 消息通知（飞书为主）—— after_script + CI_JOB_STATUS 成败通知、python/curl 选型、父子流水线条件 include 同名 job 合并坑 |
| `x-ai-backend-mysql` | 后端非生产 MySQL 安全连接 —— 公网只读 MCP、SSH 私网隧道、仓库外密钥文件与手动 stdio 兜底 |

## 文档

技能设计与实施记录见 [项目文档索引](docs/README.md)。

## 本地接入

每个技能目录直接放在仓库根，作为唯一事实来源。通过软链接挂到 Claude Code 的全局技能目录，编辑任意一侧都会同步：

```bash
git clone git@github.com:zhentai-sn/zhentai-skills.git ~/code/zhentai-skills

for s in x-ai-apifox-mcp x-ai-backend-lib-release x-ai-ci-deploy x-ai-docs-builder x-ai-feishu-doc x-ai-frontend-deploy x-ai-git-sync x-ai-gitflow x-ai-log-cls-trace x-ai-middleware-storage x-ai-nginx-domain x-ai-pkg-publish x-ai-sdd x-ai-server-deploy x-ai-private-env-ops x-ai-ssh-remote x-ai-webhook-message x-ai-backend-mysql; do
  ln -s ~/code/zhentai-skills/"$s" ~/.claude/skills/"$s"
done
```

Codex Desktop 在 Windows 上从 `C:\Users\<用户名>\.agents\skills` 发现个人技能。保持本仓库为唯一事实源，可创建目录符号链接：

```powershell
$source = '\\wsl.localhost\Ubuntu\home\<user>\code\zhentai-skills\x-ai-docs-builder'
$target = "$HOME\.agents\skills\x-ai-docs-builder"
New-Item -ItemType SymbolicLink -Path $target -Target $source
```

如果 Windows 未启用开发者模式且提示需要管理员权限，先用同步安装作为降级方案：

```powershell
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path "$source\*" -Destination $target -Recurse -Force
```

降级方案中仍只修改仓库源目录；每次更新后重新执行复制命令同步 Codex 安装副本。

安装或修改技能后，新建 Codex 会话以重新加载技能列表。


## 维护约定

- 每个技能必须含 `SKILL.md`，frontmatter 的 `name` 与目录名一致。
- 脚本中的凭据一律从环境变量读取，禁止硬编码 secret/token。
- 改动直接在仓库内提交，软链接会让本地 Claude Code 立即生效。
- 涉及具体主机、域名、凭据的内容一律写成 `<占位符>`，不要提交真实地址。
