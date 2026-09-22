---
name: x-ai-log-cls-trace
description: 腾讯云 CLS 日志按 TraceID 全链路排障。用户提到查腾讯云日志、查 CLS、看后端日志、按 traceId 排查、接口报错/异常去后端查原因、保存成功但结果不对想看后端做了啥、重建调用链、全链路追踪、跨服务追一个请求、查日志主题/Topic、SearchLog 时使用。覆盖：从接口响应或 traceparent 头拿 traceId、用 DescribeTopics 找服务对应的 TopicId、用 SearchLog 按 traceId 检索、顺着同一 traceId 跨多个服务（网关→业务服务→Feign 下游）拼出完整调用链、从日志里读出请求参数/响应/耗时/Mapper SQL/Feign 目标。关键踩坑：非交互 shell 不加载 ~/.bashrc 导致新密钥读不到（报 SecretIdNotFound）；DescribeTopics 的 Limit 上限 100；SearchLog 的 From/To 是毫秒。
---

# x-ai-log-cls-trace — 腾讯云 CLS 按 TraceID 全链路排障

一个请求出问题（报错 / 返回成功但数据不对 / 行为异常），想知道后端到底做了什么：拿到这次请求的
**TraceID**，去腾讯云 CLS 把它关联的日志捞出来，按时间重建调用链，定位是哪一环、哪一行 SQL 出的问题。

核心三步：**拿 traceId → 找 TopicId → 检索**；进阶是**同一 traceId 打多个 Topic，把跨服务调用链拼起来**。

## 前提

- 环境变量：`TENCENTCLOUD_SECRET_ID`、`TENCENTCLOUD_SECRET_KEY`、`TENCENTCLOUD_REGION`（AI是 `ap-guangzhou`）。
- 依赖：`pip install tencentcloud-sdk-python`（脚本依赖它）。
- 脚本：本 skill 自带 `scripts/cls_search.py`（按 traceId 检索）、`scripts/cls_topics.py`（列/找 Topic）。

---

## ⚠️ 头号踩坑：新密钥读不到（SecretIdNotFound）

用户在自己终端 `export` 或写进 `~/.bashrc` 的密钥，**你的非交互 shell 读不到**，原因有二：

1. 非交互 bash **不加载 `~/.bashrc`**（`.bashrc` 顶部通常有「非交互直接 return」的判断，export 写在后面根本没执行到）。
2. 父进程里残留的旧值会盖住新值。

**症状**：调用报 `[TencentCloudSDKException] code:AuthFailure.SecretIdNotFound message:SecretId不存在`，
但 `echo $TENCENTCLOUD_SECRET_ID` 看着「有值」（其实是旧值）。

**解法**：每次跑脚本前，把 export 行从 `.bashrc` 直接抽出来 eval（绕过非交互 return）：

```bash
eval "$(grep -E '^export TENCENTCLOUD_' ~/.bashrc)"
# 核对是否真换成新值（看尾部几位，别打印全量）
echo "ID tail: ...${TENCENTCLOUD_SECRET_ID: -6}  region: $TENCENTCLOUD_REGION"
```

把这行 `eval` 放在**每个**调腾讯云的 Bash 命令开头（工具每次新开 shell，不继承上一条的 env）。
若用户把密钥放在别的文件（如项目 `.env`），改成 `set -a; source <那个文件>; set +a`。

> 不要让用户把密钥粘给你。让他写进 `~/.bashrc` / `.env`，你用上面的方式加载即可。

---

## Step 1 · 拿 TraceID

- **接口响应体**：AI后端统一返回 `{"code":..,"traceId":"<hex32>","data":..}` —— 直接抄 `traceId`。
- **响应头 / 抓包**：`X-Request-ID`，或 `traceparent: 00-<traceId>-<spanId>-01`（中间那段 32 位就是 traceId，跨 Feign 调用时它会原样透传，是全链路追踪的锚）。
- **用户报错截图 / 监控**：让用户给 traceId 或能定位的请求时间 + 接口路径。

也要确认**大致时间**（前后 ±30 分钟足够）和**哪个服务**（决定查哪个 Topic）。

---

## Step 2 · 找 TopicId

检索必须指定**日志主题 ID**。不知道服务对应哪个 Topic 时，按服务名关键词列出来挑：

```bash
eval "$(grep -E '^export TENCENTCLOUD_' ~/.bashrc)"
cd ~/.claude/skills/x-ai-log-cls-trace
python3 scripts/cls_topics.py user-center     # 关键词过滤；缺省列全部
# 输出： <TopicId> | <TopicName>
```

**AI Topic 命名规律**：`<服务名>-<env>-<账号后缀>`，例：

| TopicName | 说明 |
|---|---|
| `<user-center-container>` | 用户中心服务·test（TopicId 就是这串可读名） |
| `<scale-container>` | 业务服务·test |
| `<gateway-service>-test-<account-id>` | 网关·test |
| `...-dev` / `...-<test-host-b>` | dev 环境 / 另一套 test |

- 后缀 `-<account-id>` 是 test 租户/账号；选 Topic 先对齐**环境**（用户 app 连 dev 还是 test）。
- TopicId 有时是这种可读串，有时是 UUID（如 `bcefca5a-feb0-...`）——两者都直接当 TopicId 用。
- `DescribeTopics` 单页 **Limit 上限 100**（传 200 报 `InvalidParameterValue Limit Too Large`），脚本已自动翻页。

---

## Step 3 · 按 TraceID 检索

```bash
eval "$(grep -E '^export TENCENTCLOUD_' ~/.bashrc)"
cd ~/.claude/skills/x-ai-log-cls-trace
NOW=$(date +%s000); START=$((NOW-1800000)); END=$((NOW+60000))   # 时间窗：近 30 分钟
python3 scripts/cls_search.py <trace_id> <topic_id[,topic_id2]> $START $END
```

- **环境只有 `python3`，没有 `python`**——命令一律用 `python3`。
- **From/To 是毫秒**（`date +%s000` 末尾补三个 0）。查历史用 `date -d "2026-06-27 11:00:00" +%s000` 换算。
- 脚本自动尝试 `traceId` / `trace_id` / `trace-id` / `TraceId` 多种字段名，都不中再退回**全文检索** `"<trace_id>"`，按时间升序返回。
- 输出是 JSON 数组（每条含 time/level/logger/message 等），用 `python3 -c` 或 `jq` 按时间顺序读。

捞不到时：扩大时间窗、确认 Topic 选对（环境/服务）、确认 region。

---

## 进阶 · 跨服务全链路追踪

一个请求常跨多个服务（网关 → 业务服务 → 经 Feign 调下游服务），**同一个 traceId 在每个服务的 Topic 里都有日志**。
把这个 traceId 依次打到各服务的 Topic，就能拼出完整链路。判断有没有下游：业务服务日志里出现
`feign.template` 或 `请求METHOD: POST，URL :http://<内网ip>:<port>/<下游路径>`，说明它 Feign 调了别的服务——
拿同一 traceId 去那个下游服务的 Topic 再搜一遍。

**AI 后端日志里能直接读到的关键信息**（`com.<org>.common.web.aop.WebLogAspect` 打的）：

- `请求处理CLASS_METHOD : <Controller>.<method> ,请求参数：[...]` —— 进了哪个接口、**入参原文**。
- `执行响应信息:{"code":..,"data":..,"traceId":..}` + `耗时:[..]ms` —— **返回值**和耗时。
- `XxxMapper.selectList/insert/updateById ==> Preparing/Parameters/Updates` —— **实际执行的 SQL 和参数**，能看出到底写没写、写进哪张表哪个 id。
- Feign 出站请求头里的 `traceparent` 带着同一 traceId —— 这是跨服务串联的依据。

> 实战例（保存丢答案）：<user-center-service> 收到 4 题、只 UPDATE 自己的 `<answer-record-table>` 父行并经 Feign
> 调下游服务 `/<service>/answer/v1/update`；到下游服务的 Topic 用同一 traceId 一搜，看到它把 4 题全 INSERT 进
> `<answer-item-table>`（含被疑似丢失的那条）——于是定位「后端写对了，问题在前端用错 ID 回读」。

---

## 输出建议

排障结论按调用链组织，让人一眼看到根因：

- **链路概览**：traceId、涉及哪几个服务（按 Topic）。
- **关键节点**（按时间）：服务 / Controller.method / 入参或 SQL / 成功失败 / 耗时。
- **根因**：哪个服务、哪一行（SQL/响应/异常）。
- **证据**：贴关键日志行（请求参数 / Mapper SQL / 响应）。
- 必要时用接口直接 readback 复核（如按 SQL 里暴露的真实 id 再查一次接口对比）。

## 文件结构

```
x-ai-log-cls-trace/
├── SKILL.md
└── scripts/
    ├── cls_search.py   # 按 traceId 检索（多字段名 + 全文兜底，From/To 毫秒，升序）
    └── cls_topics.py   # 列/按关键词找 TopicId（自动翻页）
```
