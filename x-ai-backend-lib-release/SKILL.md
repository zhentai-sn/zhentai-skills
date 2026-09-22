---
name: x-ai-backend-lib-release
description: AI 团队 Java/Maven 公共包（SNAPSHOT 库）改动如何一路发布并生效到测试/线上环境的全链路。用户提到发公共包、发 common 包、mvn deploy、把公共库发到 Nexus、改了公共包消费方怎么生效、更新了 common 服务要重新部署吗、光重启 k8s 拉不到新包、换镜像 tag、把改动发到测试环境、<common-service> 发版 时，主动使用本 skill。覆盖两段链路：①用 IDE Maven deploy 把 SNAPSHOT 公共包发到 Nexus；②消费方服务重新构建（GitLab CI）+ k8s 换镜像 tag 部署，让新包真正生效。含 settings.xml 选型、SNAPSHOT 构建期解析心智模型、k8s 换 tag 而非重启、一份高价值踩坑清单。是 x-ai-ci-deploy（接 CI）/ x-ai-server-deploy（拉镜像上线）/ x-ai-git-sync（分叉）的上层编排 skill，Java 侧对应 Python 的 x-ai-pkg-publish。
---

# x-ai-backend-lib-release — Java 公共包改动发布到环境的全链路

一个 Maven **公共库**（如 `<common-service>`，打成 jar 供多个后端服务依赖）改了代码后，
怎样让改动**真正出现在测试/线上环境**。发包只是第一步，真正容易踩坑的是后半段——
**消费方必须重新构建，k8s 必须换镜像 tag**。本 skill 把这条链路完整串起来。

参考实现：公共库 `<common-service>`（`4.0.x-SNAPSHOT`）→ 消费方 `<admin-service>` → 腾讯云 k8s `<namespace>` 命名空间。

## ★ 一句话心智模型（先记住这个,后面全是它的推论）

> **SNAPSHOT 依赖在「构建时」被解析并打进 jar/镜像,不是运行时去 Nexus 拉。**
> 所以改了公共包 → **必须让消费方重新构建**才能吃到;
> 单纯 `kubectl rollout restart` / 重启 Pod 拉的是**同一个旧镜像**,里面还是旧公共包 = 等于没更新。

整条链路缺一不可:

```
① 公共库:merge 回 release 分支 → IDE mvn deploy → Nexus snapshots  (发包)
      ↓
② 消费方:对齐依赖版本 → 处理分叉 → push 触发 CI 重新构建(吃到新包)→ 出镜像到 CR
      ↓
③ k8s:换成「与刚 push 的 commit 一致」的新镜像 tag 部署(不是重启!)
      ↓
④ 收尾:验证接口 + 手动灌 seed SQL(如有)
```

---

## 阶段一 — 发公共包(Maven → Nexus)

### Step 1.1 先合回 release 分支

公共包要从**集成/发布分支**(如 `feature/v4.0.1`)发,别从个人 feature 分支发。
feature 分支的活先合回 release 分支(分叉了先走 [x-ai-git-sync](../x-ai-git-sync/SKILL.md))。

### Step 1.2 用 IDE 自带 Maven 点 deploy

公共库通常**没有 CI 发布流水线**,靠手动 `mvn deploy`。本机命令行大概率没有 `mvn`——
**不用装,直接用 IDE(IntelliJ/AS)自带的 Maven**:右侧 Maven 面板 → `生存期` → 双击 **`deploy`**。

它等价于:
```bash
mvn clean deploy -s <settings.xml>
```
`deploy` 生命周期会依次跑 validate → compile → **test** → package → deploy。
想干净构建就 Ctrl 同时选 `clean` + `deploy` 一起点。

### Step 1.3 ★ settings.xml 选型(最常见的翻车点)

IDE 默认用 `~/.m2/settings.xml`,而这台机器往往没有。Nexus 认证 + 私有依赖仓库配置在**同事配好的那份**里。

- **设置 → 构建工具 → Maven → 用户设置文件(User settings file)** 勾 override,指向**同事给的那份**
  (本团队实测在 `~/settings1.xml`,含 `nexus-releases`/`nexus-snapshots` 认证 + 一堆私有依赖仓库账号)。
- **不要**用**项目根目录**那个 `settings.xml`——它常是给容器/CI 用的
  (`<localRepository>/root/...</localRepository>`、且缺依赖仓库账号),本机拿它发会 **401** 或本地仓库**权限错**。

### Step 1.4 版本决定发到哪个仓库

- `x.y.z-SNAPSHOT` → **snapshots** 仓库(`.../repository/maven-snapshots/`),产出**时间戳构件**
  (如 `<common-service>-4.0.1-<snapshot-timestamp>-74.jar`,`-74` = 第 74 次快照,会滚动更新)。
- `x.y.z`(无 SNAPSHOT)→ **releases** 仓库,不可覆盖(正式发布,通常配 tag 门禁)。

### Step 1.5 成功判据

日志出现这三样即成功:
- `BUILD SUCCESS`
- `Uploaded to nexus-snapshots: .../<artifact>-<时间戳>.jar`
- `maven-metadata.xml` 被更新(版本级 + artifact 级两处)——这决定别人按 `-SNAPSHOT` 能否指到你这次的构件

---

## 阶段二 — 让消费方吃到新包并上环境

### Step 2.1 对齐依赖版本

确认消费方 `pom.xml` 依赖的公共包版本**和你刚发的一致**:
```xml
<artifactId><common-service></artifactId>
<version>4.0.1-SNAPSHOT</version>   <!-- 别停在 4.0.0-SNAPSHOT -->
```
不一致 → 消费方重建也拿不到你的改动。

### Step 2.2 处理本地分叉后 push,触发 CI 构建

消费方分支若和远端分叉(ahead/behind),先走 [x-ai-git-sync](../x-ai-git-sync/SKILL.md) 同步,再 push。
push 会触发 GitLab CI(引用公司 `maven/universal-ci.yml`,详见 [x-ai-ci-deploy](../x-ai-ci-deploy/SKILL.md)),
CI 构建镜像并推到 `<internal-cr-host>/ai/<服务名>`,镜像 tag 形如
`feature_<branch>_<shortsha>-<date>`(如 `feature_v4.0.1_62087498-20260720`)。

**为什么 CI 一定能吃到最新快照**(公司模板已内置两道保险,自搭 CI 要注意):
- build 命令带 **`-U`**(`--update-snapshots`,强制去 Nexus 核对最新快照);
- before_script 里 `find /root/.m2/repository/com/<org> -name maven-metadata-local.xml -delete`,
  删掉私包本地元数据逼 Maven 重新解析。
- 二者叠加 → 即便 runner 缓存了 `.m2`,也绝不会用到旧快照。

> ⚠️ push 属于对外操作。若用户设定了「推送需手动确认」,**到这一步先停下让用户 push**,别自动推。

### Step 2.3 ★ k8s 换镜像 tag 部署(不是重启)

等 CI 绿了,去 k8s(本团队用**腾讯云容器服务控制台**)更新 Deployment:

- 定位到对应 Deployment(如集群 `<k8s-cluster>` / 命名空间 `<namespace>` / `<admin-service>-test`)→ 更新 Pod 配置 → **选择镜像版本**。
- **选「与你刚 push 的 commit 一致」的那个 tag**(按 shortsha 对,如 `62087498`),而不是列表里更早的那个。
- **镜像拉取策略 `IfNotPresent` 这时没问题**:tag 是全新的,本地没有,会去 CR 拉新镜像。
  (只有「复用同一个 tag + IfNotPresent」才会拉到旧镜像——所以我们坚持换新 tag。)
- **不要勾「用镜像 ENV 替换当前容器自定义环境变量」**——会冲掉你在 Deployment 里配的
  `NACOS_HOST`/`Namespace`/`JAVA_OPTS` 等自定义变量。
- 确定 → 更新 → Pod 滚动重建。

> 命令行等价物(若走 kubectl):`kubectl set image deploy/<name> <container>=<repo>:<新tag> -n <ns>`。
> **切忌只 `kubectl rollout restart` 而不换 image**——那是用原镜像重启,改动不生效。

### Step 2.4 收尾

- **验证**:调消费方受影响的接口,确认新字段/新行为出现(如某业务对象新增字段是否出现)。
- **seed SQL**:若本次改动带了测试数据 SQL(常在 `docs/sql/*.sql`),那是**手动**在目标环境的库里执行的,和镜像无关,别漏。

---

## 踩坑清单(本 skill 最值钱的部分)

| 现象 | 真因 | 处理 |
|---|---|---|
| 本机 `mvn: command not found` | 没装 CLI Maven | 用 **IDE 自带 Maven** 点 deploy,不用装 |
| deploy 报 **401 / 认证失败** | 用了项目根的 `settings.xml`(无 Nexus 认证或指向容器) | 改用同事配的 `~/settings1.xml` |
| deploy 报 localRepository **权限错** | settings 里 `<localRepository>/root/...` 本机没权限 | 换成同事那份(UNC/家目录路径),或删该行用默认 |
| 重启了 Pod 但改动没生效 | 只 rollout restart、镜像 tag 没变 → 拉旧镜像 | **换成新 commit 对应的 tag** 再部署 |
| 换了配置但环境变量全乱 | 勾了「镜像 ENV 替换自定义变量」 | 别勾,保留 Deployment 里的自定义变量 |
| 消费方重建了还是没新东西 | 依赖版本没对齐(如还写 4.0.0) | 先把消费方 pom 版本对到你发的版本 |
| CI 构建吃到旧公共包 | runner 缓存 `.m2`、没强制刷快照 | 确认 build 带 `-U` + 删 `com.<org>` 本地元数据(公司模板已内置) |
| 从个人 feature 分支发包 | 发布分支选错 | 先合回 release 分支(`feature/vX.Y.Z`)再发 |

---

## 关联 skills

- [x-ai-git-sync](../x-ai-git-sync/SKILL.md) — 消费方/公共库分支和远端分叉时,先同步再 push
- [x-ai-ci-deploy](../x-ai-ci-deploy/SKILL.md) — 消费方接公司 GitLab CI 模板 + Dockerfile 的细节
- [x-ai-server-deploy](../x-ai-server-deploy/SKILL.md) — 若消费方是单机 docker compose 而非 k8s,拉镜像上线走这个
- [x-ai-pkg-publish](../x-ai-pkg-publish/SKILL.md) — Python 公共包发布(本 skill 的 Java/Maven 对应物)
