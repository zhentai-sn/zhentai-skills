---
name: x-ai-apifox-mcp
description: 给 Claude Code / Agent 接入 Apifox MCP，并用它读取项目接口（OpenAPI）信息。用户提到配置/接入 apifox mcp、连 apifox、把 apifox 接口喂给 AI、读 apifox 接口定义、统计某模块有多少个接口、查某接口的参数/请求体/响应字段、导出/解析 apifox 的 OpenAPI(OAS)、对照 apifox 核对前后端契约 时使用。覆盖：用 `claude mcp add` 在用户级配好 apifox-mcp-server（token + 项目ID）、连通性自检、三个 MCP 工具(read_project_oas / read_project_oas_ref_resources / refresh_project_oas)的用法、以及读 OAS 时的两大坑——输出超长落盘需脚本解析、导出无目录/tag 须按 path 前缀归类模块。关键踩坑：MCP 工具在会话启动时加载，`claude mcp add` 之后必须重启 Claude Code 才出现；工具名带按项目变化的哈希后缀，用 ToolSearch `+apifox` 找。
---

# x-ai-apifox-mcp — 接入并使用 Apifox MCP 读接口

让 Claude 能直接读 Apifox 项目里的接口定义（参数、请求体、响应字段、接口数量），
不用手动复制粘贴或导出文件。本质两件事：**① 配 MCP server（一次性）→ ② 用三个工具读 OAS**。

## 速查

| 步 | 动作 | 命门 |
|---|---|---|
| ① 配 | `claude mcp add apifox --scope user ...` | 配完**必须重启 Claude Code**，工具才进会话 |
| ② 找工具 | ToolSearch `+apifox` | 工具名带项目哈希后缀（`..._ieocx5`），不是固定名 |
| ③ 读 | `read_project_oas_*` | 输出超长会**落盘到文件**，用脚本解析，别硬读 |
| ④ 归类 | 按 path 前缀分组 | 导出**无目录/无 tag**，「用户中心」=path 前缀 `/<user-center-db>` |
| ⑤ 同步 | `refresh_project_oas_*` | Apifox 改了接口后先 refresh，否则读到旧缓存 |

---

## Step ① 配置 MCP server（一次性）

### 先备两样东西

| 要素 | 去哪拿 |
|---|---|
| **访问令牌** `afxp_...` | Apifox → 右上头像 → 账号设置 → **API 访问令牌** → 新建 |
| **项目 ID**（纯数字） | 项目 → 设置 → 基本设置；或项目 URL 里的数字段 |

### 配到用户级（推荐，所有项目可用、不进仓库）

```bash
claude mcp add apifox --scope user \
  --env APIFOX_ACCESS_TOKEN=<你的令牌afxp_...> \
  -- npx -y apifox-mcp-server@latest --project=<项目ID>
```

- 写进 `~/.claude.json`（用户级），**不会**落到项目仓库，token 不外泄。
- 一个项目一个 server 实例；要接多个项目，换个名字再 add 一次（如 `apifox-xxx`）。
- 删除：`claude mcp remove apifox -s user`。

### 自检连通

```bash
claude mcp get apifox          # 看到 Status: ✔ Connected 即可
claude mcp list | grep apifox  # 同样应为 ✔ Connected
```

> ⚠️ **最大的坑**：`✔ Connected` 只代表 server 进程起得来，**当前会话仍看不到它的工具**——
> MCP 工具 schema 是**会话启动时**注入的。`claude mcp add` 之后**必须重启 Claude Code（或新开会话）**，
> apifox 的工具才会出现。配完先别急着用，重启再说。

---

## Step ② 在会话里找到工具

apifox-mcp-server 暴露 3 个工具，但**名字带按项目变化的哈希后缀**（如 `_ieocx5`、`_6m7c42`），
不能假定固定名。用 ToolSearch 找：

```
ToolSearch  query="+apifox"
```

拿到的三件套（`*` 是项目哈希后缀）：

| 工具 | 作用 |
|---|---|
| `read_project_oas_*` | 读整个项目的 OpenAPI 3.1 spec（路径、方法、参数、schema 引用） |
| `read_project_oas_ref_resources_*` | 读被 `$ref` 引用的资源（schemas / responses / securitySchemes 详情） |
| `refresh_project_oas_*` | 刷新缓存：Apifox 改了接口后先调它再读 |

> 若 ToolSearch 返回空：多半是没重启（见 Step ①），或 server 没连上（回 Step ① 自检）。

---

## Step ③ 读 OAS —— 输出超长会落盘，用脚本解析

直接调 `read_project_oas_*` 时，稍大的项目（几百个接口）输出会**超出 token 上限**，
MCP 会把全文**保存到一个 `.txt` 文件**并在返回里给出路径，形如：

```
.../tool-results/mcp-apifox-read_project_oas_<hash>-<ts>.txt
```

文件就是一份合法 **OpenAPI 3.1 JSON**（`components` 用 `$ref` 指向 index.json）。
**不要逐块硬读几千行**，用脚本一次算出来。本 skill 自带 `scripts/oas_stats.py`：

```bash
# 1) 总览：接口总数 + 按 path 一级前缀（≈ 模块）分布
python3 scripts/oas_stats.py <落盘的txt路径>

# 2) 数某个模块的接口数 + 二级细分（如「用户中心」）
python3 scripts/oas_stats.py <落盘的txt路径> --prefix /<user-center-db>

# 3) 列出某前缀下的全部接口路径（method + path）
python3 scripts/oas_stats.py <落盘的txt路径> --prefix /<service>/<resource> --list
```

> 💡 本团队的 WSL/Linux 环境**没装 jq**，别用 `jq`；用 Python（自带）解析。

---

## Step ④ 归类模块 —— 按 path 前缀，不是 tag

**关键认知**：Apifox 导出的 OAS **不保留目录(folder)结构**，全部接口挂在一个「默认模块」、
**没有 tag**。所以你**不能**按 tag 过滤出「用户中心」这种 Apifox 目录。

正确做法：**按 URL path 前缀归类**。本团队后端路径自带业务前缀，和 Apifox 目录基本一一对应：

| Apifox 目录（约） | path 前缀 |
|---|---|
| 用户中心 | `/<user-center-db>` |
| 用户中心-定时任务 | `/<user-center-db>_job`（一级段不同，单独算） |
| 平台 | `/platform` |

报数时讲清口径：「按 path 前缀 `/<user-center-db>` 计 = N 个」，并提示目录/前缀的对应是约定、非强一致。

---

## Step ⑤ 看单接口细节 / 同步更新

- **某接口的入参/响应字段**：先从 OAS 里定位该 path 的 operation，里面字段多是 `$ref`；
  再用 `read_project_oas_ref_resources_*` 把引用的 schema 展开读。
- **Apifox 那边刚改过接口**：先调 `refresh_project_oas_*` 刷新，再 `read_project_oas_*`，
  否则读到的是旧缓存。

---

## 典型任务串法

- 「统计 X 模块有多少接口」→ Step②找工具 → read 落盘 → `oas_stats.py --prefix /X`。
- 「查 Y 接口的请求体字段」→ read 落盘 → grep path 定位 operation → ref_resources 展开 schema。
- 「对照 Apifox 核对前后端契约」→ refresh → read → 按 path 把前端调用点逐个比对参数名/必填/类型。

## 踩坑清单（按出现频率）

1. **配完没重启 → 工具不出现**。`✔ Connected` ≠ 工具可用，会话启动才注入。重启 Claude Code。
2. **工具名猜错**。带项目哈希后缀，永远先 ToolSearch `+apifox` 拿真实名，别写死。
3. **硬读超长 OAS**。几百接口必落盘，逐块读几千行又慢又爆 token，一律走 `oas_stats.py` / Python。
4. **想按 tag 分模块**。导出无 tag、无目录，只能按 path 前缀；跨一级段的（`/<user-center-db>_job`）要单独说明。
5. **环境没 jq**。用 Python 标准库解析 JSON。
6. **读到旧接口**。Apifox 改动后先 `refresh_project_oas_*`。
