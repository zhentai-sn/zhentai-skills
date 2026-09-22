# 通过 SSH 隧道连接私网 MySQL

## 目录

1. [适用场景](#适用场景)
2. [保存凭据](#保存凭据)
3. [建立隧道](#建立隧道)
4. [加载连接](#加载连接)
5. [排障](#排障)
6. [安全规则](#安全规则)

## 适用场景

用于非生产 MySQL 只能从跳板机访问，且 Codex 需要直接查询而不操作 Navicat 的情况。典型拓扑：

```text
Codex/本机 → 127.0.0.1:<local-port> → SSH jump-host
→ <private-mysql-host>:3306
```

先确认环境、跳板别名、目标地址、库名和账号权限。不要从截图推断密码，也不要解密 Navicat 注册表。

## 保存凭据

推荐把每个连接放在仓库外的独立文件：

```text
%USERPROFILE%\.codex\secrets\<connection-name>.env
```

示例：

```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_PORT=13306
MYSQL_USER=<database-user>
MYSQL_PASS=<database-password>
MYSQL_DB=<database-name>
```

兼容用户已创建的 `MYSQL_PASSWORD`/`MYSQL_DATABASE`，加载时映射到 MCP 使用的
`MYSQL_PASS`/`MYSQL_DB`；新文件统一使用 MCP 原生变量名。

创建目录并限制为当前 Windows 用户读写：

```powershell
$dir = "$env:USERPROFILE\.codex\secrets"
$file = Join-Path $dir "<connection-name>.env"
New-Item -ItemType Directory -Force $dir
notepad $file
icacls $file /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
```

只检查文件是否存在和文件名，不输出内容。记事本可能追加 `.txt`，或因路径拼接错误生成错误文件名；
在同一 secrets 目录内确认绝对路径后再重命名。

## 建立隧道

先验证 SSH 别名：

```bash
ssh <jump-host> 'hostname'
```

创建后台隧道：

```bash
ssh -f -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:<local-port>:<private-mysql-host>:3306 <jump-host>
```

`ExitOnForwardFailure=yes` 能避免命令看似成功但端口未监听。再次创建前先检查端口：

```powershell
Test-NetConnection 127.0.0.1 -Port <local-port> -InformationLevel Quiet
```

Windows 查不到 `Get-NetTCPConnection` 监听项但 `Test-NetConnection=True` 时，监听者可能位于 WSL；
这仍表示隧道可用。不要因看不到 Windows PID 重复创建。

## 加载连接

PowerShell 中把密钥加载到当前子进程环境，不打印值：

```powershell
$cfg = @{}
foreach ($line in Get-Content -LiteralPath $secretFile) {
  if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
  $key, $value = $line -split '=', 2
  $cfg[$key.Trim()] = $value.Trim()
}

$env:MYSQL_HOST = $cfg.MYSQL_HOST
$env:MYSQL_PORT = $cfg.MYSQL_PORT
$env:MYSQL_USER = $cfg.MYSQL_USER
$env:MYSQL_PASS = if ($cfg.MYSQL_PASS) { $cfg.MYSQL_PASS } else { $cfg.MYSQL_PASSWORD }
$env:MYSQL_DB = if ($cfg.MYSQL_DB) { $cfg.MYSQL_DB } else { $cfg.MYSQL_DATABASE }
$env:ALLOW_INSERT_OPERATION = 'false'
$env:ALLOW_UPDATE_OPERATION = 'false'
$env:ALLOW_DELETE_OPERATION = 'false'
```

然后优先：

1. 使用当前会话已经加载的 `mysql_query` MCP。
2. MCP 未加载时，按主 `SKILL.md` 的手动 stdio 流程驱动
   `@benborla29/mcp-server-mysql`。
3. 本机已有 `mysql`、`mysql2` 或其他驱动时，可直接用当前进程环境连接；查询结果不得包含密码。

首次连接只执行：

```sql
SELECT DATABASE(), CURRENT_USER(), VERSION();
```

再查目标表。雪花 ID 统一 `CAST(... AS CHAR)`，探索性查询带 `LIMIT`。

## 排障

按层次判断，不把工具问题误判成数据库问题：

| 现象 | 判断与处理 |
| --- | --- |
| 本地端口不通 | 隧道未建立、端口冲突或跳板不可达 |
| `Access denied for user ...` | 网络已通；账号未授权目标 MySQL 或密码不匹配 |
| `npx` 初始化超时 | 先预热 MCP 包，再重启会话 |
| `npm error Maximum call stack size exceeded` | 本机 npx/npm 缓存或解析异常，不是数据库认证失败；可使用已缓存包或现有驱动，勿删除整个缓存 |
| MCP 工具未出现 | 当前会话启动时未加载；使用手动 stdio 或重启 Codex |
| 查询为空 | 连接成功但条件未命中；复核环境、库名、ID 精度和 `deleted` 语义 |

手动驱动成功后，若需要长期使用，再配置独立 MCP 名称，例如 `mysql_pre_read`；不要覆盖已有公共 CDB
的 `mysql` 配置。MCP 配置若必须包含口令，只放在用户级配置或加载密钥文件的本地包装命令中，
不提交到仓库。

## 安全规则

- 密钥文件必须在仓库外，禁止纳入 Git。
- 不在命令行参数、日志、回答或异常中回显密码。
- 默认关闭 MCP 的三个写操作开关。
- 高权限账号只代表“技术上可写”，不代表“用户已授权写”。
- 用户明确授权非生产 DML 后，仍需事务、精确谓词、行数断言和执行后独立回查。
- 不使用该流程连接生产库。
