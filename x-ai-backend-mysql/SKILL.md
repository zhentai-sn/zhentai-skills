---
name: x-ai-backend-mysql
description: AI 团队后端测试/开发 MySQL 查询与安全连接。把腾讯云 CDB 公网库接成 Codex/Claude Code 的 MySQL MCP(@benborla29/mcp-server-mysql,多库只读模式)，或通过 SSH 跳板和仓库外密钥文件连接 pre/preview 私网 MySQL。用户提到查后端数据库、连接 <backend-api-service>/<backend-api-service> MySQL、看表数据、核对落库、查 <user-center-db>/scale/<business-db>/<metrics-db>、配置 mysql mcp、不使用 computer_use 连接数据库、通过 <test-host-main> 转发 10.x:3306、SHOW TABLES/SELECT 时使用。覆盖只读 MCP、手动 stdio 兜底、私网隧道、密钥文件和连接排障。不含生产库；写操作必须另有明确授权。
---

# x-ai-backend-mysql — 非生产 MySQL 安全连接与查询

AI 团队后端各服务使用腾讯云 CDB 和私网 MySQL 承载 dev/test/pre 数据。
本 skill 让 Codex/Claude Code 通过 **MySQL MCP** 或 SSH 隧道直接查数，不依赖 Navicat 或
`computer_use`。公共 CDB 连接全程只读；私网写连接默认也只查询，DML 需要用户明确授权。

⚠️ 这里只处理**测试/开发/pre 库，不含生产库**；查到的数据不能当作生产真值。

## 连接信息

| 项 | 值 |
|---|---|
| Host | `<mysql-host>`(公网,本机直连可达) |
| Port | `<mysql-port>` |
| User | `<readonly-account>`(**只读**) |
| Pass | **不落本文件**;已存于 `~/.claude.json` 的 mysql MCP 配置里,或找团队要 |
| DB | 不指定 → **多库模式**,可跨库 `库名.表名` 查 |

> 🔐 口令不写进 skill/仓库/脚本。取用时从已配好的 MCP 读:
> `python3 -c "import json;print(json.load(open('$HOME/.claude.json'))['projects']['<项目路径>']['mcpServers']['mysql']['env']['MYSQL_PASS'])"`
> ,或让用户临时 `export MYSQL_PASS=...`。

## 私网 pre/preview

需要经 SSH 跳板访问 `10.x:3306`、用户希望把密码放在 Codex 可读但不进 Git 的位置，或当前会话
没有加载 MySQL MCP 时，完整读取
[references/private-mysql-via-ssh.md](references/private-mysql-via-ssh.md)。

连接与业务操作分开授权：

- 建隧道、连通性检查、`SELECT` 属于只读诊断。
- 即使账号有写权限，也先将 MCP 写开关保持关闭。
- `INSERT/UPDATE/DELETE/DDL` 只在用户明确要求当前非生产补数/修复时执行，并限制库、表、主键、
  tenant/entity/instance/seed marker，使用事务和行数断言。

## 一次性建连(Claude Code)

`<你的密码>` 现填(建完就存进 ~/.claude.json,后续不用再输):

```bash
claude mcp add mysql \
  -e MYSQL_HOST=<mysql-host> \
  -e MYSQL_PORT=<mysql-port> \
  -e MYSQL_USER=<readonly-account> \
  -e MYSQL_PASS='<你的密码>' \
  -e ALLOW_INSERT_OPERATION=false \
  -e ALLOW_UPDATE_OPERATION=false \
  -e ALLOW_DELETE_OPERATION=false \
  -- npx -y @benborla29/mcp-server-mysql
```

- `--` 后是启动命令(npx 拉起第三方包),前面 `-e` 是喂给它的连接信息
- 不带 `MYSQL_DB` = 多库模式,能看到账号有权限的所有库
- 三个 `ALLOW_*=false` = 只读闸,别改
- 默认写 local 作用域(`~/.claude.json` 本项目段,不进 git);想全局用加 `-s user`

建完的工具名是 **`mysql_query`**(单参数 `sql`)。

## ⚠️ 第一次必踩:Failed to connect 不是配置错

`claude mcp add` 之后 `claude mcp list` 大概率先显示 `mysql: ✘ Failed to connect`。
**真因是 npx 首次要联网下载 `@benborla29/mcp-server-mysql`,冷启动慢过健康探针超时**,
跟 host/账号/密码无关。处理:

1. 手动跑一次把包缓存预热:`timeout 30 npx -y @benborla29/mcp-server-mysql </dev/null`(挂住是正常的,它在等 stdio)
2. 再 `claude mcp list | grep mysql` → 应变 `✔ Connected`
3. **重启 Claude Code**:MCP 工具在会话启动那刻定格,启动时若还是 failed,本会话内就调不到 `mysql_query`;预热后重启才会把工具正式载入

判断"是不是配置错"别看 `claude mcp list` 一次结果,用下面的手动兜底实测握手。

## 不重启也能查:手动 stdio 兜底

会话里 `mcp__mysql__mysql_query` 还没载入时,直接驱动 MCP 服务器查数(也是验证连通性的权威手段)。
先从已配好的 MCP 读出连接信息、再发三段 JSON-RPC:

```bash
# 从 ~/.claude.json 的 mysql MCP 配置导出连接环境变量(含只读闸)
eval "$(python3 - <<'PY'
import json,os,glob
cfg=json.load(open(os.path.expanduser('~/.claude.json')))
env=None
for proj in cfg.get('projects',{}).values():
    m=proj.get('mcpServers',{}).get('mysql')
    if m: env=m['env']; break
for k,v in (env or {}).items():
    print(f"export {k}='{v}'")
PY
)"

SQL="SELECT COUNT(*) FROM <user-center-db>_test.some_table"   # ← 换成你的查询
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
"{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"mysql_query\",\"arguments\":{\"sql\":\"$SQL\"}}}" \
| timeout 40 npx -y @benborla29/mcp-server-mysql 2>/dev/null \
| tail -1 | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['content'][0]['text'])"
```

要点:三行 JSON-RPC 依次是 initialize → initialized 通知 → tools/call;
结果 JSON 在最后一行,`content[0].text` 是查询结果、`content[1].text` 是耗时。
SQL 里有单引号时优先用双引号包 SQL 值、或走 heredoc,避免 shell 转义地狱。

Codex 会话优先使用已加载的 MySQL MCP。工具没有出现在当前会话时，先检查 MCP 配置和服务器
预热状态；不需要打开 Navicat。手动 stdio 也是连接方式，不属于电脑 UI 操作。

## 库清单与环境后缀

**后缀 = 环境**:`_dev`(开发) / `_test`(测试主) / `_test_b`(测试 B,第二套);无后缀的是历史/共享库。同一服务三套后缀结构基本一致、只是数据不同。

多库模式下每个微服务一个库,库名即服务名。**首次连上先自己列一遍,不要凭猜**:

```sql
SHOW DATABASES;                          -- 按前缀归类,识别出环境后缀规律
SELECT table_schema, COUNT(*) AS tables  -- 按表数排序,最大的通常是核心域
  FROM information_schema.tables
 GROUP BY table_schema ORDER BY tables DESC;
```

列完之后建议在本地记一份「服务前缀 → 含义 → 代表库(表数)」的对照,下次直接查表。**这份对照属于内部拓扑,不要提交进公开仓库。**

多库模式下**查询务必写全 `库名.表名`**(如 `<some-db>_test.assessment`),否则没有默认库会报错。
探索一个库先:`SHOW TABLES FROM <some-db>_test` → `DESCRIBE <some-db>_test.<表>` → 再 `SELECT`。

## 只读红线

- 账号 `<readonly-account>` + 三个 `ALLOW_*=false` 双保险,DDL/DML 一律被 MCP 层拦下
- 查询自觉带 `LIMIT`,大库(<user-center-db> 125+ 表)别裸 `SELECT *` 全表拉
- 这套是测试/开发库,查到的数不代表生产;要生产数据另找有权限的通道,别改本 skill 的账号
- 口令不外泄:不把 `MYSQL_PASS` 明文写进任何会提交/被分享的文件
- 私网账号可能具备写权限；不得因为账号叫 `root` 就默认获得 DML 授权
