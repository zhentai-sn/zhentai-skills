# Python 项目文档画像

本参考适用于常见 Python 库、FastAPI 服务和内部业务服务。仓库已有约定始终优先。

## 根目录

| 文件 | 建议内容 |
| --- | --- |
| `README.md` | 定位、能力、Python 版本、安装/启动最短路径、配置入口、测试命令、docs 导航 |
| `AGENTS.md` | 包管理器、关键架构约束、代码入口、测试分层、lint/type check、提交规范 |
| `pyproject.toml` | 依赖、工具和脚本的机器事实源；文档不手抄完整配置 |
| `CHANGELOG.md` | 库或版本化服务的用户可见变化 |
| `.env.example` | 可公开配置样例；guide/runbook 解释语义，不写真实 secret |

## 代码与文档对应

| 文档声明 | 优先核对 |
| --- | --- |
| 启动命令 | `pyproject.toml` scripts、Makefile、容器入口、`main.py` |
| Python 版本 | `requires-python`、CI 镜像、Dockerfile |
| 配置项 | Pydantic settings、环境变量读取、`.env.example` |
| HTTP 路由 | FastAPI router、OpenAPI、acceptance tests |
| 响应与错误 | schema、exception handler、middleware、SDD |
| 依赖与 extras | `pyproject.toml`、lock 文件 |
| 测试层级 | pytest markers、tests 目录、CI jobs |
| 部署流程 | Dockerfile、compose、CI 配置、runbook |
| 可观测性 | logging 初始化、中间件、OTel 配置、运维查询方法 |

## 推荐 docs 画像

```text
docs/
├── README.md
├── research/       # 框架选型、性能测试、第三方能力验证
├── sdd/            # API、事件、数据模型、错误契约
├── plans/          # 架构设计和分阶段实施
├── guides/         # 本地开发、SDK/API 使用、扩展方法
├── runbooks/       # 部署、配置中心、迁移、故障恢复
├── issues/         # 技术债、开放决策、评审发现
└── solutions/      # 已验证的线上问题或复杂缺陷解法
```

小型 Python 库通常无需 runbooks；纯服务仓通常需要 runbooks，但未必需要 changelog。不要为“完整”创建没有内容的目录。

## README 最短路径

推荐只保留：

1. 项目解决什么问题。
2. 支持的 Python 与包管理器。
3. 安装或同步依赖。
4. 最小配置。
5. 启动和健康验证。
6. lint / test 主命令。
7. 指向 docs 索引。

完整环境变量表、Nacos 键说明、所有接口示例、部署差异和排障过程下沉到 guide/runbook/SDD。

## API 与响应规范

先确认对象属于 Python SDK 返回模型、HTTP response envelope、SSE/WebSocket 帧还是事件总线消息。它们可以共享字段命名原则，但除非有正式决策，不默认共享同一外层结构。

出现以下内容时联用 `x-ai-sdd`：

- 统一响应 envelope。
- HTTP 状态码与业务码映射。
- trace ID、分页和错误详情字段。
- 鉴权失败、参数校验和下游异常语义。
- 向后兼容、版本迁移和验收用例。

若现状不统一，先在 `issues/` 记录差异、风险、证据和待决策项；不要直接在 guide 中宣布新规范。

## 验证命令

优先运行仓库已有入口，例如：

```bash
make lint
make test
uv run pytest
uv run ruff check .
uv run mypy src
```

不要凭习惯选择命令。先读取 Makefile、`pyproject.toml` 和 CI 配置，并按文档改动风险选择验证范围。
