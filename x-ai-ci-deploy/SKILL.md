---
name: x-ai-ci-deploy
description: AI 团队 Python 业务服务接入公司 GitLab 通用 CI 模板 + Docker 镜像构建 + 单机部署配置。用户提到接入 CI、配 .gitlab-ci.yml、写 Dockerfile、构建镜像、推镜像、部署服务、docker compose 上线、复用团队既有的 CI 流程、新服务接 CI/CD 时，主动使用本 skill。覆盖 .gitlab-ci.yml（引用 ci-templates）、Dockerfile（腾讯云内部 CR 基础镜像 + 多阶段 + uv + Nexus 私服）、docker-compose.prod.yml（拉镜像形态）三件套，以及一份高价值踩坑清单。是 x-ai-pkg-publish（发包）的姊妹 skill（部署）。
---

# x-ai-ci-deploy — AI 团队 Python 服务接入 CI + Docker 部署

把一个公司 Python 业务服务接入**统一 GitLab CI 模板**，CI 自动构建镜像并推到腾讯云 CR，
再用 docker compose 单机部署。参考实现：`<algorithm-service>-<business>` / `<composer-service>` /
`<knowledge-service>` 三个仓同一套模式。

## 三件套速查

| 文件 | 位置 | 作用 |
|---|---|---|
| `.gitlab-ci.yml` | **repo 根目录** | 引用公司模板，触发 CI 流水线 |
| `Dockerfile` | **repo 根目录**（不可放子目录！） | 多阶段构建镜像 |
| `docker-compose.prod.yml` | repo 根目录 | 部署：拉 CR 镜像 + 起容器 |

## 镜像源分层惯例（关键：每层用不同的源）

| 拉什么 | 用的源 | 说明 |
|---|---|---|
| 基础镜像（FROM） | `<internal-cr-host>/cicd/python:3.12-slim` | 腾讯云内部 CR，**别用 `python:3.12-slim`**（Docker Hub 会超时） |
| apt 系统包 | `mirrors.tencent.com` | 替换 Debian 源（仅当 builder 要 apt 装编译依赖时） |
| pip 公共包（如 uv） | `mirrors.cloud.tencent.com/pypi/simple/` 或 `mirrors.aliyun.com/pypi/simple/` | 装 uv 前必配，否则直连 PyPI 卡死 |
| 私有包（x-ai-common 等） | `<nexus-host>`（Nexus 私服） | 由 pyproject 的 `[[tool.uv.index]]` 指定 |

---

## Step 1 — 前置确认

向用户/从 pyproject 确认这几个值（后面模板里要替换）：

- **服务名**（kebab-case，= 仓库名）：如 `<knowledge-service>`
- **包名**（snake_case，`src/` 下目录名）：如 `x_knowledge_server`
- **镜像仓库地址**：`<internal-cr-host>/ai/<服务名>`
- **监听端口**：如 `8000`
- **启动命令**：uvicorn factory（`uvicorn <pkg>.main:create_app --factory`）还是
  `python -m <pkg>.run`——看仓库现有 `CMD` / 入口
- **pyproject 是否有 `readme = "..."` 字段**（影响 Step 3 的 COPY，见踩坑 #2）

---

## Step 2 — 写 `.gitlab-ci.yml`（根目录）

整个文件就这么短——逻辑全在公司共享模板里：

```yaml
include:
  - project: '<group>/<ci-group>/<ci-templates>'
    ref: 'master'
    file: 'python/universal-ci.yml'

variables:
  # 必填：Docker 镜像仓库地址
  DOCKER_IMAGE_REPO: "<internal-cr-host>/ai/<服务名>"
```

模板流水线：`checkout → config → build → docker → notify`
- 任意分支 push 或打 tag 都触发；`build` 阶段 `uv sync` 验依赖，`docker` 阶段
  `docker build` 推镜像，`notify` 成功/失败都发飞书。
- 镜像 tag：`<分支>_<sha8>-<日期>`；`master`+tag 时 `master_<tag>_<sha>_<日期>`。

---

## Step 3 — 写 `Dockerfile`（根目录，多阶段）

**必须放 repo 根目录**（模板的 `docker build ... .` 写死根目录上下文，且会显式校验，见踩坑 #1）。
下面是经过实战验证的模板，替换 `<...>` 占位符：

```dockerfile
# 多阶段构建。构建上下文 = repo root。
# 基础镜像走腾讯云内部 CR，避免 Docker Hub 超时；x-ai-common 从 Nexus 私服装。
ARG PYTHON_IMAGE=<internal-cr-host>/cicd/python:3.12-slim

# ── builder ──
FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# pip 走腾讯云公网镜像装 uv（避免直连 PyPI 卡死，见踩坑 #3）。
RUN pip install --no-cache-dir -i https://mirrors.cloud.tencent.com/pypi/simple/ uv==0.8.3

WORKDIR /build

# Nexus 凭据：CI 传 --build-arg PYPI_USER/PYPI_PASSWORD；默认值对齐 pyproject 内嵌凭据。
# 映射到 uv 命名 index 环境变量作冗余兜底（index name 见 pyproject 的 [[tool.uv.index]] name）。
ARG PYPI_USER=admin
ARG PYPI_PASSWORD=<nexus 密码>
ENV UV_INDEX_<INDEX_NAME 大写下划线>_USERNAME=${PYPI_USER} \
    UV_INDEX_<INDEX_NAME 大写下划线>_PASSWORD=${PYPI_PASSWORD}

# 若 pyproject 有 readme = "README.md"，README.md 必须一并 COPY（见踩坑 #2）。
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── runtime ──
FROM ${PYTHON_IMAGE} AS runtime

ARG GIT_SHA=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GIT_SHA=${GIT_SHA} \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app/src \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder --chown=app:app /build/.venv /app/.venv
COPY --from=builder --chown=app:app /build/src /app/src

USER app
EXPOSE <端口>

# 二选一，看仓库入口。注意：用 python -m，别用 .venv/bin/uvicorn 控制台脚本（见踩坑 #8）。
CMD ["python", "-m", "uvicorn", "<pkg>.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "<端口>"]
# CMD ["python", "-m", "<pkg>.run"]
```

> `<INDEX_NAME 大写下划线>`：pyproject 的 `[[tool.uv.index]] name` 转大写、连字符→下划线。
> 例：`name = "private-nexus"` → `UV_INDEX_PRIVATE_NEXUS_USERNAME`。
> uv 文档：[Authentication](https://docs.astral.sh/uv/concepts/indexes/#authentication)。

如果 x-ai-common 的某些依赖需要编译（构建报缺 gcc/缺头文件），在 builder 加 apt 段
（先换腾讯云源再装），参考 `<composer-service>/Dockerfile` 顶部；多数情况有 wheel 不用。

---

## Step 4 — pyproject 的私服 index（凭据惯例）

凭据**内嵌在 index URL**（对齐参考仓惯例，密码进 git；团队当前接受这点）：

```toml
[[tool.uv.index]]
url = "https://admin:<nexus 密码>@<nexus-host>/repository/pypi-hosted/simple/"
name = "private-nexus"

[[tool.uv.index]]
url = "https://mirrors.aliyun.com/pypi/simple/"
default = true
```

> 想更安全（密码不进 git）可去掉 URL 内嵌凭据、改纯环境变量
> `UV_INDEX_<NAME>_USERNAME/PASSWORD` 注入——但代价是本地 `uv sync` / `make up`
> 都要先 export。**默认按参考仓惯例（内嵌）**，除非用户明确要求挪出 git。

---

## Step 5 — 写 `docker-compose.prod.yml`（拉镜像部署形态）

```yaml
# 部署用：从腾讯云 CR 拉 CI 构建好的镜像，不本地构建。
services:
  app:
    image: ${IMAGE_NAME:-<internal-cr-host>/ai/<服务名>}:${IMAGE_TAG:-latest}
    container_name: ${CONTAINER_NAME:-<服务名>}
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "${HOST_PORT:-<端口>}:<端口>"
    healthcheck:
      # 有 /health 端点就用它探活（无需镜像内装 curl）；没有就用 TCP 端口探活。
      test:
        - "CMD"
        - "python"
        - "-c"
        - "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:<端口>/health',timeout=3).status==200 else 1)"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
```

无 `/health` 端点时换 TCP 探活：
`"import socket; s=socket.create_connection(('localhost',<端口>),timeout=3); s.close()"`

---

## Step 6 — 核对 `.dockerignore`

确认**没有**排除构建期需要的文件。最容易踩的是 README.md（见踩坑 #2）：

```
# README.md 不能排除：pyproject 的 readme 字段构建期需要它。
docs/
AGENTS.md
# README.md   ← 别在这里
.env
.env.*
!.env.example
.git/
__pycache__/
.venv/
```

---

## Step 7 — GitLab CI/CD 变量（用户在 GitLab 侧确认）

模板引用但需配置的变量（通常上级 group `<group>`/`<subgroup>` 已继承）：

| 变量 | 用途 |
|---|---|
| `DOCKER_USERNAME` / `DOCKER_PASSWORD` | 腾讯云 CR `<internal-cr-host>` 登录 |
| `PYPI_USER` / `PYPI_PASSWORD` | Nexus 私服（装 x-ai-common） |

报错 `Project not found` 多半是模板项目 `ci-templates` 对本仓没读权限——找运维放通。

---

## Step 8 — 验证

**本地构建验证**（可选，先确认 Dockerfile 通）：
```bash
GIT_SHA=$(git rev-parse --short HEAD) docker compose -f docker/docker-compose.yml up -d --build
# 或 make up（若仓库有 Makefile）
```

**触发 CI**：commit + push（任意分支都触发），去 GitLab → CI/CD → Pipelines 看。

**部署**（服务器上拉镜像）：
```bash
docker login <internal-cr-host>
cp docker/.env.example .env          # 填 Nacos 等配置
IMAGE_TAG=<CI 产物 tag> docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f app
curl -fsS http://localhost:<端口>/health   # 冒烟
```

---

## 踩坑清单（最值钱，每条都来自实战）

**#1 Dockerfile 必须在 repo 根目录。** 模板的 docker stage 是
`docker build --build-arg ... -t ... .`（**无 `-f`**，上下文写死 `.`），还会显式
`if [ ! -f "Dockerfile" ]; then 报错`。Dockerfile 放 `docker/` 子目录直接 fail。
那个看着能指定子目录的 `PYTHON_PROJECT_DIR` 变量是摆设，build/docker 阶段没用它。
→ 把 Dockerfile 放根目录；连带改 `docker/docker-compose.yml` 的 `dockerfile:` 指向、
  Makefile 里旧路径引用、文档里的路径。

**#2 README.md（或 pyproject `readme` 指向的文件）构建期必须可得。** 第二次
`uv sync` 要把本项目装成 editable wheel，hatchling 校验 `readme` 字段会读该文件，
缺了报 `OSError: Readme file does not exist`。两个动作缺一不可：
(a) Dockerfile `COPY pyproject.toml uv.lock README.md ./`；
(b) `.dockerignore` **不能**排除 README.md（很多脚手架默认把 README.md 当"运行时不需要"
排除了，但构建期需要）。

**#3 pip 装 uv 前必须配国内镜像。** builder 里 `pip install uv` 默认直连 pypi.org，
国内会长时间卡在下载 uv wheel（~18MB）。加 `-i https://mirrors.cloud.tencent.com/pypi/simple/`
（或阿里云）。注意这是 **pip 这一层**；uv 自己拉包走 pyproject 的 index。

**#4 基础镜像用内部 CR，不用 Docker Hub。** `FROM python:3.12-slim` 会让本地/服务器
拉镜像时撞 `dial tcp ... i/o timeout`（Docker Hub 国内不可达）。换
`<internal-cr-host>/cicd/python:3.12-slim`（需先 `docker login` 该 CR）。
若本地 `/etc/docker/daemon.json` 配过失效的 registry-mirror（如 `docker.xpg666.xyz` 返回 522），
换可用的或直接用内部 CR。

**#5 `SecretsUsedInArgOrEnv` 警告非阻塞。** build 时出现
`Do not use ARG or ENV for sensitive data (ARG "PYPI_PASSWORD")` 是 BuildKit lint 警告，
**不影响构建**，参考仓也一样有。是 build-arg 传密码的固有提示，可忽略。

**#6 shared 分支（dev/master）别 force push。** 若已 push 的 commit 又被 `--amend`，
本地与远端分叉，直接 push 被拒。**别 `--force`**（会重写他人依赖的历史）。正确做法：
`git reset --soft origin/<branch>` 把改动退回工作区，再**追加一个新 commit**，push 即 fast-forward。

**#7 CI 的 `build` 阶段用的是 Docker Hub 的 `python:3.12-slim`。** 那是公司 runner 环境
（不是我们 Dockerfile 的 FROM），通常已配镜像加速。若 CI 第一次就卡在拉 `python:3.12-slim`，
是 runner 没配加速，找运维，不是代码问题。

**#8 venv 跨路径 COPY → 控制台脚本 shebang 失效，CMD 用 `python -m`。** uv 在 builder
的 `/build/.venv` 建 venv，控制台脚本（`uvicorn`/`gunicorn` 等）首行 shebang 被写死成
`#!/build/.venv/bin/python`；COPY 到 runtime 的 `/app/.venv` 后该路径不存在，容器启动报
`exec /app/.venv/bin/uvicorn: no such file or directory` 并 `Restarting (255)` 崩溃重启。
→ CMD 用 `python -m uvicorn ...`（或 `python -m <pkg>.run`），走 PATH 里的 `python`
符号链接（指向基础镜像真实解释器，跨路径不受影响），**不要**用 `CMD ["uvicorn", ...]`
这种控制台脚本形式。这是个**潜伏 bug**：构建/推镜像都成功，只在容器真正启动时才暴露。

**#9 editable 安装把构建期路径烧死 → 运行期 ModuleNotFoundError，补 PYTHONPATH。**
与 #8 同源：builder 第二次 `uv sync` 默认把本项目装成 **editable**，site-packages 里
留的引用指向构建期 `/build/src`；COPY 到 runtime `/app/src` 后引用悬空，启动报
`ModuleNotFoundError: No module named '<pkg>'`。→ runtime 加 `ENV PYTHONPATH=/app/src`
（对齐参考仓，最低风险）；或改 builder 为 `uv sync --frozen --no-dev --no-editable`
把项目装成真 wheel 进 site-packages（更干净，运行期不依赖 /app/src，但需验证）。
同样是**潜伏 bug**，只在容器启动时暴露。

**#10 非 root 用户写运行期目录（logs / 缓存）要构建期建好并 chown。** 用 `USER app`
（非 root）跑时，应用启动写日志会 `mkdir('logs')`（相对 WORKDIR `/app`）；`/app` 由
WORKDIR 以 root 建，app 用户无权在其下创建子目录，报
`PermissionError: [Errno 13] Permission denied: 'logs'`。→ `USER` 指令前
`RUN mkdir -p /app/logs /app/.nacos_cache && chown app:app /app /app/logs /app/.nacos_cache`
（对齐参考仓）。这是镜像跨路径 COPY 三连坑（#8/#9）之外的**第四个潜伏启动坑**。

**#11 非 root + bind mount → 写权限被 root 属主盖掉，用具名卷。** compose 里
`./somedir:/app/somedir` 的 **bind mount**：宿主目录由 docker daemon 以 **root** 创建，
挂进容器后会**盖掉**镜像里 `chown` 给 app 的同名目录，非 root 的 app 用户写不进去
（如 Nacos 缓存 `PermissionError: '/app/.nacos_cache/.nacos_tmp_*.yaml'`）。
→ 需要持久化又跑非 root：用**具名卷**（`nacos_cache:/app/.nacos_cache` + 顶层
`volumes: {nacos_cache:}`）——具名卷首次挂载会**继承镜像目录的属主**（app），可写且持久。
（参考仓 <composer-service> 用 bind mount 没事，是因为它**以 root 跑**、没有 `USER app`。）
注意：本机 `docker run` 不带 `-v` 时测不出这个——本地验证要用**真 compose**（含挂卷）复现。

> #2/#8/#9/#10/#11 都是「构建/推镜像成功、容器启动才暴露」的潜伏 bug。强烈建议接入新服务后
> **先本地 `docker build` + `docker run` 把容器真正跑起来**（哪怕 Nacos 连不上，也能一次性
> 验证 README/shebang/PYTHONPATH/写权限四类问题），别等推到 CI、部署到服务器才发现，省下
> 多轮「push → CI 构建 → 部署」往返。本机无 buildx 时，可临时
> `sed 's/--mount=type=cache,target=[^ ]* //' Dockerfile` 去掉 cache mount 再用传统 builder 构建。

---

## 与 x-ai-pkg-publish 的关系

- `x-ai-pkg-publish`：把**公共包**（如 x-ai-common）发布到 Nexus。
- `x-ai-ci-deploy`（本 skill）：把**业务服务**接入 CI、构建镜像、部署。
  业务服务通过 pyproject 的 Nexus index **消费** x-ai-common。
