---
name: x-ai-nginx-domain
description: 为服务器上的 HTTP 服务配置 Nginx 域名接入、DNSPod A/CNAME 解析和 HTTPS 端到端验收。用户提到给服务挂域名、配置或新增 Nginx server_name、把域名反代到某端口、给 test/pre 服务加域名、在 DNSPod 添加解析、域名不生效、检查证书匹配、验证 DNS/HTTPS 时使用。覆盖：确认主机与上游端口、复用现有 vhost 和团队通配符证书、生成独立配置、nginx -t 后热加载、添加 DNS 记录，以及从公共 DNS 和服务端验证真实解析、证书和上游路由。不负责申请或续签证书、修改应用代码、开放安全组端口或生产域名迁移。
---

# x-ai-nginx-domain — Nginx + DNSPod 域名接入

把一个已在服务器端口正常响应的 HTTP 服务，通过 Nginx、HTTPS 和 DNSPod 暴露为团队域名，并完成端到端验收。

```text
域名 → DNS A/CNAME 记录 → 服务器 80/443 → Nginx server_name → proxy_pass → 应用端口
```

## 红线

- 先只读发现，再变更。必须确认环境、SSH 主机、完整域名、Nginx 所在主机和上游地址。
- 不覆盖用途不明的同名 vhost。目标配置已存在时先展示有效差异；修改前创建带时间戳备份。
- 不盲目新增重复 DNS 记录。发现相同主机记录已有 A/CNAME 时，先核对目标与线路；替换已有记录必须明确告知影响。
- 所有 Nginx 变更必须先 `nginx -t`，通过后才 `systemctl reload nginx`；不用 `restart`，不重启应用容器。
- 校验失败只撤销本次精确变更，不删除其他配置，不执行宽泛清理。
- 不打印 `.env`、容器全部环境变量、证书私钥或 DNS 凭据。若需 SSH，沿用 `x-ai-ssh-remote` 的凭据规则。
- 不因“已有 HTTPS 域名”就假设证书覆盖新域名；必须使用 `openssl ... -checkhost` 验证。
- 给管理后台或中间件配置公网域名前，说明暴露风险；本 Skill 不代替登录鉴权、来源限制或 VPN。

## Step 1 — 建立只读基线

先收集四个值：

```text
SSH_TARGET=<服务器别名或 user@host>
FQDN=<完整域名，如 <app-pre-host>>
UPSTREAM=<Nginx 可访问的地址，如 127.0.0.1:13000>
REFERENCE_VHOST=<同环境/同服务的现有配置，可为空>
```

确认 Nginx 与应用：

```bash
ssh <SSH_TARGET> '
  hostname
  command -v nginx
  systemctl is-active nginx
  nginx -v
  docker ps --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"
  ss -ltnp
'
```

只查看相关配置，避免无界输出整个 `/etc/nginx`：

```bash
ssh <SSH_TARGET> '
  find /etc/nginx/conf.d -maxdepth 1 -type f -name "*.conf" -print | sort
  grep -RInE "<服务关键词>|<候选域名>|proxy_pass" /etc/nginx/conf.d --include="*.conf"
'
```

验证上游自身可用：

```bash
ssh <SSH_TARGET> \
  'curl -sS -o /dev/null -w "status=%{http_code}\n" http://<UPSTREAM>/'
```

只有 Nginx 与应用同机时才优先使用 `127.0.0.1:<PORT>`；跨主机反代使用可达的内网地址。不要无故绕公网 IP。

若应用依赖公开基址（如 `NEXTAUTH_URL`、`AUTH_URL`、回调 URL），只读取部署配置中明确命名的非敏感字段；禁止用宽泛 `docker inspect` 输出全部环境变量。发现应用重定向到旧域名或 IP 时，先修正应用公开基址再验收。

## Step 2 — 生成独立 vhost

优先复用同主域名、同证书、同应用类型的现有 vhost，只改：

1. 两处 `server_name`。
2. `proxy_pass` 上游地址。
3. 确有差异的上传大小、超时或 WebSocket 头。

通用模板：

```nginx
server {
    listen 80;
    server_name <FQDN>;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name <FQDN>;

    ssl_certificate /etc/nginx/ssl/<主域名>/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/<主域名>/privkey.key;

    client_max_body_size 100m;

    location / {
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_pass http://<UPSTREAM>;
    }
}
```

不要机械加入 `Connection "upgrade"`：普通 HTTP 服务可省略；Langfuse、WebSocket 或流式 UI 可保留。证书路径必须来自服务器现状，不能猜。

### 新增配置

目标文件不存在时，创建独立文件：

```text
/etc/nginx/conf.d/<用途>.conf
```

可以复制最接近的配置后手动改两处：

```bash
cp /etc/nginx/conf.d/<参考>.conf /etc/nginx/conf.d/<新配置>.conf
vi /etc/nginx/conf.d/<新配置>.conf
```

复制前先用 `test ! -e <目标>` 防止覆盖。

### 修改已有配置

先备份：

```bash
cp /etc/nginx/conf.d/<配置>.conf \
   /etc/nginx/conf.d/<配置>.conf.bak.$(date +%Y%m%d%H%M%S)
```

备份文件不要长期留在会被 `include /etc/nginx/conf.d/*` 加载的扩展名中；确认主配置只加载 `*.conf`，或把备份放到 `/etc/nginx/backup/`。

## Step 3 — 校验、热加载与 DNS 前验收

先检查，再热加载：

```bash
nginx -t
systemctl reload nginx
systemctl is-active nginx
```

若 `nginx -t` 失败，恢复备份或移走本次新增文件，再重新执行 `nginx -t`；不要 reload 失败配置。

DNS 尚未配置时，用 `--resolve` 强制命中新 vhost：

```bash
curl -skS -o /dev/null \
  -w "status=%{http_code} redirect=%{redirect_url}\n" \
  --resolve <FQDN>:443:127.0.0.1 \
  https://<FQDN>/
```

再独立验证证书主机名；`curl -k` 只能证明路由，不能证明证书有效：

```bash
openssl s_client -connect 127.0.0.1:443 -servername <FQDN> </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -checkhost <FQDN>
```

预期同时满足：

- `nginx -t` 成功。
- Nginx 仍为 `active`。
- 强制解析 HTTPS 返回应用预期状态。
- `Hostname <FQDN> does match certificate`。
- 原有参考域名仍可访问。

## Step 4 — 配置 DNSPod

优先查找可用的 DNSPod/Tencent Cloud connector、API 或 `tccli`。没有专用能力时，使用用户已登录的浏览器；若浏览器不可控，给用户精确字段并等待其保存，不索取 DNS 凭据。

记录类型选择：

- 服务直接位于固定公网 IPv4：使用 `A`。
- 公司已有稳定入口域名或负载均衡域名：使用 `CNAME`。
- 不确定时检查同环境相邻记录，不凭空选择。

DNSPod A 记录常用字段：

| 字段 | 值 |
|---|---|
| 主机记录 | 只填子域名前缀，如 `langfusepre`，不填完整域名 |
| 记录类型 | `A` |
| 线路类型 | `默认` |
| 记录值 | Nginx 服务器公网 IPv4 |
| TTL | 沿用相邻记录；无约定时保留默认值（常见 600 秒） |
| 状态 | 启用 |

保存前复述最终映射：

```text
<FQDN> → <PUBLIC_IP>
```

DNS 只决定流量到哪台服务器，不携带端口；80/443 到应用端口的映射由 Nginx 完成。DNS 保存后不需要再次 reload Nginx。

## Step 5 — 公网端到端验收

至少从 Nginx 主机或独立网络查询一次真实 DNS：

```bash
dig +short A <FQDN>
dig @119.29.29.29 +short A <FQDN>
```

没有 `dig` 时：

```bash
getent ahostsv4 <FQDN> | awk '!seen[$1]++ {print $1}'
```

注意：启用代理/TUN 的本机可能返回 `198.18.0.0/15` 一类合成地址。这是代理内部映射，不是 DNSPod 的真实 A 记录；改从服务器、权威 DNS 或公共递归 DNS 查询。

验证公网 HTTPS：

```bash
curl -sS -I --connect-timeout 10 --max-time 20 https://<FQDN>/

echo | openssl s_client -connect <FQDN>:443 -servername <FQDN> 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -checkhost <FQDN>
```

最后确认它是目标环境，而不只是“某个登录页”：

- 核对有效 Nginx 配置中的 `server_name → proxy_pass`。
- 调用 `/health`、`/version` 或环境标识接口（若有）。
- test/pre 页面外观相同时，不以 UI 相似作为环境证据。
- 对照容器端口、访问日志时间和代表性响应，确保没有落到默认 vhost。

## 验收报告

完成后只报告已确认事实：

```text
域名：<FQDN>
DNS：<FQDN> → <实际解析 IP>
Nginx：<配置文件> → <UPSTREAM>
HTTPS：<状态码>
证书：<匹配/不匹配与到期时间>
原域名回归：<通过/失败>
待办：<DNS 传播、应用公开基址、安全组等；无则写无>
```

## 回滚

- Nginx：把本次新增文件移到不被 include 的备份目录，或恢复精确备份；`nginx -t` 成功后 reload。
- DNS：禁用或删除本次精确记录。若本次是修改已有记录，恢复原值；说明 TTL 缓存可能延迟回滚生效。
- 不删除证书、不停止应用、不清理容器或数据。

## 与其他 Skill 的边界

- SSH 登录、密钥与非交互远程命令：`x-ai-ssh-remote`
- 镜像拉取、Compose 启动与容器健康：`x-ai-server-deploy`
- 安全组、云防火墙或服务器部署：使用相应部署运行手册，本 Skill 只处理域名入口
