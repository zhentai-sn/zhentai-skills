---
name: x-ai-server-deploy
description: AI 团队 Python 服务部署到服务器并验证的运行手册——登录腾讯云 CR 拉镜像 → docker compose 起容器 → 确认健康。用户提到部署上线、把服务部署到服务器/测试机、登录镜像仓库、docker login、拉镜像跑起来、docker compose up 上线、服务起不来排查、确认部署成功、冒烟验证、端口冲突、容器连不上 Nacos/依赖 时，主动使用本 skill。是 x-ai-ci-deploy（CI 构建镜像）的下游姊妹 skill：CI 把镜像推上 CR 之后，本 skill 接手「服务器上怎么登录、拉、起、验」。覆盖 CR 登录与凭据时效、镜像 tag 定位、compose+.env 部署、健康确认，以及多服务同机的端口/网络踩坑清单。
---

# x-ai-server-deploy — AI 团队 Python 服务上服务器部署 + 验证

把 CI 已经构建并推到腾讯云 CR 的镜像，在**部署主机**上登录、拉取、起容器、确认健康。
和 `x-ai-ci-deploy` 配对：那个管「源码 → 镜像」（三件套 + CI），本 skill 管「镜像 → 跑起来」。

镜像由 CI 产出，地址形如 `<internal-cr-host>/ai/<服务名>:<分支>_<sha8>-<日期>`。

## 三步速查

| 步 | 动作 | 命门 |
|---|---|---|
| ① 登录 | CR 加 IP 白名单 + `docker login` | 白名单没进会"假装网络不通"；临时 token 会过期；WSL credsStore 坑 |
| ② 起 | `docker compose -f docker-compose.prod.yml up -d` | tag 是 **8 位** sha；端口冲突换 `HOST_PORT` |
| ③ 验 | `docker ps` healthy + logs + `curl /health` | 容器在独立网，依赖地址不能写 `localhost` |

## 前置

- **部署主机**能连：腾讯云 CR（拉镜像）、**Nacos**（本服务对 Nacos fail-fast，连不上直接崩）、
  以及业务依赖（PG / Redis / RabbitMQ / <内部采集服务> 端口 / 数据中心 等，按服务用到的算）。
- 主机已装 docker + docker compose v2。
- 镜像已由 CI 构建成功（GitLab → 仓库 → CI/CD → Pipelines 的 `docker` 阶段绿）。
- 部署目录（如 `~/deploy/<服务名>/`）里有 `docker-compose.prod.yml`（从仓库根目录拷或 checkout）。

---

## Step 1 — 配置 CR 拉取权限（IP 白名单 + 登录）

镜像仓库 `<internal-cr-host>` 是私有 CR，拉取要过**两道**：实例侧的 IP 白名单
（决定这台机器**能不能连到** CR），加上 `docker login`（决定**有没有凭据**拉）。新部署机两道都要配。

### 1.1 把部署机 IP 加入 CR 访问白名单（先做）

腾讯云容器镜像服务（TCR）实例默认拒绝白名单外的来源。新机器第一次拉之前，要把它的**出口 IP**
加进实例的访问白名单，否则 `docker login` / `docker pull` 会**连接超时或被拒**（表现为 `EOF` /
`SSL_ERROR_SYSCALL` / `i/o timeout`，跟"网络不通"一个症状，容易误判）。

- 公网拉取：TCR 控制台 → 对应实例 → **访问控制 / 公网访问白名单** → 加这台机器的**公网出口 IP**。
  查本机出口 IP：`curl -s https://ifconfig.me` 或 `curl -s ip.sb`。
- 内网/VPC 拉取：在实例的 **VPC 网络访问** 里放通部署机所在 VPC/子网。
- 拿不准实例名、改不了白名单 → 找运维加（说明部署机 IP + 要拉的命名空间 `ai/<服务名>`）。

> 已经在白名单里的老部署机（同机已有别的服务在拉镜像）跳过这步。判断方法：
> `curl -sS -m 10 https://<internal-cr-host>/v2/` 能握上手（返回 401 而非超时）就说明 IP 通了。

### 1.2 docker login（配置拉取凭据）

```bash
docker login <internal-cr-host> --username <UIN> --password <TOKEN>
# 出现 "Login Succeeded" 即可。
# 警告 "Using --password via the CLI is insecure" 可忽略；更稳的是 --password-stdin：
#   echo "<TOKEN>" | docker login <internal-cr-host> --username <UIN> --password-stdin
```

> **凭据来源**：腾讯云容器镜像服务（TCR）控制台 → 访问凭证（临时/长期）。`--username` 是子账号 UIN，
> `--password` 是该账号的访问 token。**临时 token 自带过期时间（exp）**，过期后 `docker login` 会失败、
> 拉镜像报 401/unauthorized——重新到控制台取新 token 再 login 即可。
> 〔团队若有固定的 DOCKER_USERNAME/DOCKER_PASSWORD（CI 用的同一对），也可直接用那对长期凭据。〕

**踩坑 · WSL/装了 Docker Desktop 的机器 `error getting credentials`**：
`~/.docker/config.json` 里若有 `"credsStore": "desktop.exe"`，docker 会优先调这个凭据助手，
WSL 里够不到它就报 `error getting credentials - err: exit status 1`，即便 `auths` 里已有 token 也用不上。
绕过（不动全局配置）：

```bash
mkdir -p /tmp/dk && python3 -c "
import json; c=json.load(open('$HOME/.docker/config.json'))
c.pop('credsStore',None); c.pop('credHelpers',None)
json.dump(c, open('/tmp/dk/config.json','w'))"
DOCKER_CONFIG=/tmp/dk docker pull <internal-cr-host>/...   # 用临时 config 拉
```

---

## Step 2 — 定位镜像 tag 并起容器

### 2.1 拿对 tag

镜像 tag 格式：`<分支>_<sha8>-<日期>`，例如 `dev_e3dd787a-20260611`。
**`<sha8>` 是 8 位 commit sha，不是 git 默认的 7 位**——这是高频错。

```bash
git rev-parse --short=8 HEAD     # 取 8 位 sha 自己拼，或
# 直接看 CI 的 docker 阶段日志 / 腾讯云 CR 控制台的镜像版本列表，复制现成 tag 最稳。
```

tag 写错的症状：`failed to resolve reference "...:<tag>": ... not found`。核对 sha 位数与日期。

### 2.2 准备 `.env`（关键，决定能否起来）

部署目录放 `.env`。本服务对 **Nacos fail-fast**，且绝大部分运行期配置在 Nacos
（dataId `<服务名>.yaml`）里，`.env` 主要是 bootstrap + 部署机特有项：

```bash
# Nacos 连接（必填，缺了/连不上 → 启动即崩）
NACOS_SERVER_ADDRESSES=<宿主局域网IP>:8848
NACOS_NAMESPACE=<环境>
NACOS_DATA_ID=<服务名>.yaml
NACOS_GROUP=DEFAULT_GROUP

# 部署机特有项（放 .env 持久化，免得每次 up 都手敲前缀）
HOST_PORT=8001                         # 见 Step 2.3 端口冲突
IMAGE_TAG=dev_e3dd787a-20260611        # 这次要部署的 tag
```

> docker compose 会自动读同目录 `.env` 做 `${HOST_PORT}` / `${IMAGE_TAG}` 变量替换，
> 也会作为容器 env_file 注入（容器不识别的变量无害）。
>
> ⚠️ **端口/依赖选择是部署机特有的，放服务器 `.env`，别改仓库里的 compose**（仓库默认保持通用），
> 这样别的部署机不受影响。

### 2.3 起容器

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f app
```

**踩坑 · `Bind for 0.0.0.0:8000 failed: port is already allocated`**：
多服务同机时宿主端口常被占（如 8000 被 <knowledge-service> 占着）。先查占用：

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep <端口>
sudo ss -ltnp | grep :<端口>
```

解法二选一：停掉占用方（`docker rm -f <容器>`），或**换宿主端口**——
compose 已留 `HOST_PORT` 开关，容器内仍是 8000，只改宿主映射：

```bash
# 在 .env 里设 HOST_PORT=8001（或临时前缀 HOST_PORT=8001 docker compose ... up -d）
# 结果是 0.0.0.0:8001->8000/tcp
```

---

## Step 3 — 确认部署成功

### 3.1 容器状态

```bash
docker ps --filter name=<容器名> --format '{{.Status}}'
# 期望从 "Up X (health: starting)" 在 start_period(默认30s) 后变 "Up X (healthy)"。
# 若是 "Restarting (N)" → 崩溃重启，直奔 logs 第一条 error。
```

### 3.2 启动日志看三条递进

```bash
docker compose -f docker-compose.prod.yml logs --tail=60 app
```

健康启动应依次出现：
1. Nacos 连上（无 connection refused / timeout）
2. `settings.loaded nacosDataId=<服务名>.yaml`
3. `app.serving` ← 到这条才算活

### 3.3 冒烟

```bash
curl -fsS http://localhost:<HOST_PORT>/health     # 永远 200（存活探针）
curl -fsS http://localhost:<HOST_PORT>/readyz     # 依赖就绪才 200（Nacos/PG/外部接口）
curl -fsS http://localhost:<HOST_PORT>/version    # 核对 gitSha=<本次部署的 sha8>
```

`/version` 的 `gitSha` 必须等于你部署的 tag 里那个 sha——对不上说明拉/起的是旧镜像。

---

## 踩坑清单（每条来自实战）

**#1 镜像 tag 的 sha 是 8 位不是 7 位。** `dev_e3dd787a-20260611` 而非 `dev_e3dd787-...`。
写错报 `not found`。用 `git rev-parse --short=8 HEAD` 或直接从 CR 控制台复制现成 tag。

**#2 端口冲突（多服务同机）。** 集成/测试机上常并排跑十几个容器，8000 这类端口大概率被占
（典型：<knowledge-service> 占 8000）。用 `.env` 的 `HOST_PORT` 换宿主端口，容器内端口不变。

**#3 容器在独立 bridge 网，够不到其他容器的 `localhost`。** 这是最隐蔽的坑：Nacos/PG/采集端
等依赖即便和本服务在**同一台主机**，也是各自独立容器；本服务容器里的 `localhost` 指它自己，
连不到它们。依赖地址（`NACOS_SERVER_ADDRESSES`、Nacos 里的 `PG_HOST` / `<SERVICE>_BASE_URL` 等）
要写**宿主局域网 IP**（如 `<宿主局域网-ip>`），不能写 `localhost` / `127.0.0.1`。
〔这些服务都 `0.0.0.0:port` 发布到宿主，所以走宿主 IP 能到。〕

**#4 对 Nacos fail-fast。** 正式入口在 Nacos 连不上或 dataId 缺关键字段时**直接退出**，
不降级。症状是容器 `Restarting`、logs 第一条就是 Nacos 相关 error。先确认 `.env` 的 Nacos 地址用了
宿主 IP（见 #3）、namespace/dataId 对、且 Nacos 上 `<服务名>.yaml` 配齐了业务字段
（VOLC_* / PG_* / ASSESSMENT_* / LANGFUSE_* / LLM_API_KEY 等，按服务用到的算）。

**#5 CR 临时 token 过期。** `docker login` 用的 token 自带 exp；过几小时/几天后拉镜像报
401/unauthorized。重到腾讯云 CR 控制台取新 token 重新 login。

**#5b IP 没进白名单"假装网络不通"。** 部署机 IP 不在 TCR 白名单时，`docker login`/`pull` 报
`EOF` / `SSL_ERROR_SYSCALL` / `i/o timeout`——和真·网络不通同症状，极易误判成"VPN 没连"。
鉴别：`curl -sS -m 10 https://<internal-cr-host>/v2/` 若**秒断/超时**而别的网站正常，
多半是白名单问题（见 Step 1.1），不是网络。401 才说明 IP 通了、只是没登录。

**#6 WSL/Docker Desktop 的 `credsStore: desktop.exe` 够不到。** 见 Step 1 末尾的临时
`DOCKER_CONFIG` 绕过法。本机直接部署的 Linux 服务器通常没这问题（无 desktop credStore）。

**#7 `/health` 200 但 `/readyz` 不 200。** `/health` 是存活探针恒 200，`/readyz` 才反映依赖就绪。
两者不一致 = 进程活着但某个依赖（Nacos/PG/外部接口）没就绪，按 #3/#4 查依赖连通性。

---

## 与 x-ai-ci-deploy 的关系

- `x-ai-ci-deploy`：源码 → 镜像。写 `.gitlab-ci.yml` / `Dockerfile` / `docker-compose.prod.yml` 三件套，
  CI 构建并推镜像到 CR。
- `x-ai-server-deploy`（本 skill）：镜像 → 跑起来。在部署主机登录 CR、拉镜像、compose 起容器、验健康。
  消费的正是上一个 skill 在 CR 里留下的镜像。
