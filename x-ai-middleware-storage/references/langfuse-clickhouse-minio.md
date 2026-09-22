# Langfuse + ClickHouse + MinIO 存储治理配方

## 目录

1. [适用范围](#适用范围)
2. [只读发现](#1-只读发现)
3. [ClickHouse 占用拆分](#2-clickhouse-占用拆分)
4. [MinIO 容量和增长](#3-minio-容量和增长)
5. [PostgreSQL 与 Redis](#4-postgresql-与-redis)
6. [判断 system.text_log](#5-判断-systemtext_log)
7. [安全清理 system.text_log](#6-安全清理-systemtext_log)
8. [日志降级与 7 天 TTL](#7-日志降级与-7-天-ttl)
9. [热加载验证](#8-热加载验证)
10. [变更后检查](#9-变更后检查)
11. [Windows → SSH → Bash 踩坑](#10-windows--ssh--bash-踩坑)

## 适用范围

用于 Docker/Compose 部署的 Langfuse，常见组件为 Web、Worker、ClickHouse、MinIO、PostgreSQL 和 Redis。所有名称都必须先发现，示例名不能直接当成事实。

## 1. 只读发现

先确认宿主机和容器状态：

```bash
df -hT /
docker ps --format '{{.Names}}\t{{.Status}}'
docker ps --format '{{.Names}}' | grep -i langfuse
```

从容器标签定位 Compose 项目，但要验证路径仍存在：

```bash
docker inspect -f \
  'project={{index .Config.Labels "com.docker.compose.project"}} workdir={{index .Config.Labels "com.docker.compose.project.working_dir"}} files={{index .Config.Labels "com.docker.compose.project.config_files"}}' \
  <CLICKHOUSE_CONTAINER>
```

盘点挂载：

```bash
for c in $(docker ps --format '{{.Names}}' | grep -i langfuse); do
  docker inspect -f '{{range .Mounts}}{{println .Type "|" .Name "|" .Source "|" .Destination}}{{end}}' "$c"
done | sort -u
```

`du` 扫描 MinIO 数百万小文件可能几十秒仍无结果。先设置硬超时；超时后切换 MinIO 管理指标，不要反复全盘扫描。

## 2. ClickHouse 占用拆分

确认客户端可用：

```bash
docker exec <CLICKHOUSE_CONTAINER> clickhouse-client --query 'SELECT version()'
```

按表查看压缩占用：

```sql
SELECT database, name,
       formatReadableSize(total_bytes) AS size,
       total_rows
FROM system.tables
WHERE total_bytes > 0
ORDER BY total_bytes DESC
LIMIT 30;
```

按月查看系统日志分区：

```sql
SELECT table, partition,
       formatReadableSize(sum(bytes_on_disk)) AS disk,
       sum(rows) AS rows
FROM system.parts
WHERE active AND database = 'system'
  AND table IN (
    'text_log', 'trace_log', 'opentelemetry_span_log',
    'query_log', 'metric_log', 'asynchronous_metric_log',
    'part_log', 'processors_profile_log'
  )
GROUP BY table, partition
ORDER BY table, partition DESC;
```

当前月系统日志日均估算：

```sql
SELECT
  formatReadableSize(sum(bytes_on_disk)) AS month_bytes,
  formatReadableSize(
    sum(bytes_on_disk) /
    (dateDiff('second', toStartOfMonth(now()), now()) / 86400)
  ) AS average_per_elapsed_day
FROM system.parts
WHERE active AND database = 'system'
  AND partition = formatDateTime(now(), '%Y%m');
```

今天是部分日。业务增长应列出每天行数，并以最近 7 个完整自然日计算平均值。

若只能估算压缩字节数，可用：

```text
表平均压缩字节/行 = system.tables.total_bytes / total_rows
某日估算压缩增量 = 当日新增行数 × 平均压缩字节/行
```

明确说明它会受大字段分布、更新版本和压缩率变化影响。

## 3. MinIO 容量和增长

优先读取 MinIO 管理 Prometheus 指标：

- `minio_cluster_usage_buckets_total_bytes`
- `minio_cluster_usage_buckets_objects_count`
- 对象大小分布指标
- 指标上次更新时间

使用已有 `mc` 别名最安全：

```bash
mc admin prometheus metrics <ALIAS> --api-version v3 \
  | grep -E 'bucket.*usage.*(bytes|objects)|usage.*bucket'
```

如果只有容器环境中的凭据：

- 在同一个远程 Shell 中读取并使用，不输出变量值。
- 不把密码拼进聊天、脚本、Shell history 或长期配置。
- 临时管理容器结束后确认已删除。

若有按日新增对象记录，可估算：

```text
平均对象字节数 = bucket_total_bytes / bucket_objects_count
某日对象增量 = 某日新增对象数 × 平均对象字节数
```

这是估算，不含文件系统元数据开销；对象大小分布明显变化时误差会增大。

## 4. PostgreSQL 与 Redis

不要打印容器密码。PostgreSQL 可在容器内复用已有环境：

```bash
docker exec <POSTGRES_CONTAINER> sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
  "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY pg_database_size(datname) DESC;"'
```

Redis 先检查持久化目录和 RDB/AOF：

```bash
docker exec <REDIS_CONTAINER> sh -lc 'du -sh /data; ls -lh /data'
```

## 5. 判断 `system.text_log`

`system.text_log` 是 ClickHouse 自身诊断日志，不是 Langfuse traces、observations、scores 或 MinIO 对象。

先读取表定义，不靠记忆判断：

```sql
SHOW CREATE TABLE system.text_log;
```

ClickHouse 的表注释通常明确说明可随时 truncate/drop。仍需检查最近错误等级，避免清掉正在排障的证据：

```sql
SELECT level, count() AS entries,
       formatReadableSize(sum(length(message))) AS message_size
FROM system.text_log
WHERE event_time >= now() - INTERVAL 24 HOUR
GROUP BY level
ORDER BY entries DESC;
```

再找主要来源：

```sql
SELECT logger_name, level, count() AS entries,
       formatReadableSize(sum(length(message))) AS message_size
FROM system.text_log
WHERE event_time >= now() - INTERVAL 24 HOUR
GROUP BY logger_name, level
ORDER BY entries DESC
LIMIT 20;
```

如果几乎全是 Debug/Trace，通常先清历史，再降低级别和设置 TTL。

## 6. 安全清理 `system.text_log`

这是不可逆操作。必须先展示精确表名、大小、日志等级分布、预计释放量和“历史诊断日志不可恢复”，取得明确确认。

确认后使用 SQL，不删除 ClickHouse 物理文件：

```sql
TRUNCATE TABLE system.text_log;
```

执行后立即验证：

```sql
SELECT name, total_rows, formatReadableSize(total_bytes)
FROM system.tables
WHERE database = 'system' AND name = 'text_log';
```

同时检查 `df -h /`、ClickHouse healthy 状态和业务表。日志写入仍开启时，清空后出现少量新行是正常现象。

## 7. 日志降级与 7 天 TTL

读取当前有效级别：

```bash
for key in logger.level text_log.level; do
  printf '%s=' "$key"
  docker exec <CLICKHOUSE_CONTAINER> clickhouse extract-from-config \
    --config-file=/etc/clickhouse-server/config.xml --key="$key"
done
```

独立覆盖文件内容：

```xml
<clickhouse>
    <logger>
        <level>information</level>
    </logger>
    <text_log>
        <level>information</level>
    </text_log>
</clickhouse>
```

写入规则：

1. 目标使用 `/etc/clickhouse-server/config.d/` 下语义明确的新文件名。
2. 若目标已存在，先读取并判断归属，不直接覆盖。
3. 写到 `.tmp`，用 `clickhouse extract-from-config` 校验两个 key。
4. 原子 `mv` 成正式文件。
5. 执行 `SYSTEM RELOAD CONFIG`；失败则移除新文件并再次 reload 回滚。
6. 从合并后的主配置读取两个 key，确认均为 `information`。

TTL 使用在线 DDL：

```sql
ALTER TABLE system.text_log
MODIFY TTL event_date + INTERVAL 7 DAY DELETE;

SHOW CREATE TABLE system.text_log;
```

TTL 删除在后台 merge 中发生，不承诺立即释放空间。刚清空的表设置 TTL 风险最低。

## 8. 热加载验证

记录 ClickHouse 时间作为 marker，执行多条代表性查询，刷新日志并等待至少一个 flush 周期：

```bash
marker=$(docker exec <CLICKHOUSE_CONTAINER> clickhouse-client \
  --query "SELECT formatDateTime(now(), '%F %T') FORMAT TabSeparatedRaw")

for i in $(seq 1 20); do
  docker exec <CLICKHOUSE_CONTAINER> clickhouse-client --query 'SELECT 1' >/dev/null
done

docker exec <CLICKHOUSE_CONTAINER> clickhouse-client \
  --query 'SYSTEM FLUSH LOGS text_log'
```

按 marker 查询新日志：

```sql
SELECT level, count(), max(event_time)
FROM system.text_log
WHERE event_time >= parseDateTimeBestEffort('<MARKER>')
GROUP BY level
ORDER BY count() DESC;
```

验证通过的标准：新窗口没有 Debug/Trace。窗口无行也可以接受，表示代表性查询低于 Information 阈值。

若仍持续产生 Debug/Trace：停止并报告热加载未生效。不要自动重启；重启 ClickHouse 需要新的授权和时间窗口。

## 9. 变更后检查

至少核对：

```bash
df -h /
docker ps --format '{{.Names}}\t{{.Status}}' | grep -i langfuse
docker inspect -f 'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{end}} started={{.State.StartedAt}}' <CLICKHOUSE_CONTAINER>
```

用 `system.tables` 检查 Langfuse 业务表仍存在且大小合理；代表性查询应避免在大表上反复 `count()` 导致验证超时。

容器内覆盖文件可跨 `docker restart` 保留，但容器重建会丢失。最终应将文件放到宿主机并在 Compose 中挂载；若当前 Compose 已删除 ClickHouse 服务定义，先恢复并评审定义，禁止直接重建遗留容器。

## 10. Windows → SSH → Bash 踩坑

- PowerShell 双引号会提前解释 `$()`、`$var` 和括号；远端脚本优先用单引号 here-string。
- PowerShell 管道会带 CRLF；远端用 `tr -d '\r' | bash` 再执行。
- 不把文件内容和多层引号塞进一条 SSH 命令。传脚本到远端标准输入，再在远端执行。
- Base64 仅用于非敏感配置文本；不要让 PowerShell 以二进制方式改写标准输入。
- 每一步检查退出码；写配置时保留临时文件、解析校验和失败回滚。
