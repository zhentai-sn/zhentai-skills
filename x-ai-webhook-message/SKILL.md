---
name: x-ai-webhook-message
description: 给 GitLab CI/CD 流水线接入 webhook 消息通知（飞书自定义机器人为主，企业微信/钉钉/Slack 同理）。用户提到 CI/CD 发飞书/webhook 通知、部署完成推消息到群、构建成功/失败通知、给流水线加 after_script 发通知、复用现有构建通知群、接入飞书机器人 webhook 时，主动使用本 skill。覆盖：after_script + CI_JOB_STATUS 成败一处搞定、python3/curl 发送选型、webhook 凭据用 CI/CD 变量 vs 硬编码降级、父子流水线 + 条件 include 下同名 job 合并的关键坑、触发时机与本地验证方法。是 x-ai-ci-deploy（接 CI）的补充（加通知）。
---

# x-ai-webhook-message — 给 GitLab CI/CD 流水线接 webhook 消息通知

把「部署 / 构建 完成」这件事，通过 webhook 推一条消息到群（飞书自定义机器人为主）。
核心就一句：**在目标 job 的 `after_script` 里，按 `$CI_JOB_STATUS` 组装消息、POST webhook**。
参考实现：`<agent-service-repo>`（后端，shell runner + curl）、`<admin-frontend-repo>`（前端，
python 镜像 + python urllib + 父子流水线条件 include）。

## 什么时候用本 skill

- 想让流水线部署/构建完成后自动往群里发通知（成功、失败、或两者）
- 复用团队现有的「构建通知群」飞书机器人
- 目标 job 定义在**共享 CI 模板**里（不在本仓），要在不动模板的前提下加通知
- 项目是**父子流水线 + 条件 include**结构（一次 push 触发多套环境/租户）

---

## 决策清单（动手前先答这几问，直接决定写法）

| 问题 | 影响 |
|---|---|
| **1. 通知挂在哪个 job？** | 通常是最终的 `deploy`（或 `build`）。挂它的 `after_script`。 |
| **2. 这个 job 在本仓还是共享模板里？** | 在本仓 → 直接加 `after_script`；在模板里 → 用**同名 job 合并**（见 Step 3）。 |
| **3. 项目是不是父子流水线 + 条件 include？** | 是 → 覆盖必须放**条件 include 的独立文件**里，否则父流水线报非法 job（**头号坑**，见 Step 3 / 踩坑 #1）。 |
| **4. job 跑在什么 runner/镜像？** | shell runner / 有 curl → 用 curl；`*-slim` 等无 curl 的镜像 → 用 `python3`（几乎一定有）。 |
| **5. webhook 怎么给流水线？** | 首选 **CI/CD Variable**（masked，需 Maintainer）；无权限时**硬编码降级**（见 Step 4）。 |
| **6. 飞书机器人开签名校验没？** | 没开 → 纯 POST 即可；开了 → body 要带 `timestamp` + `sign`（HMAC-SHA256，见附录）。 |

> 判断 4/6 的最省事办法：如果群里**已经在收**别的项目的通知，说明那个 webhook「纯 POST 能发、没开签名」，直接复用。

---

## Step 1 — 拿飞书机器人 webhook

飞书目标群 → 设置 → 群机器人 → 添加「自定义机器人」→ 复制 Webhook 地址，形如：

```
https://open.feishu.cn/open-apis/bot/v2/hook/<TOKEN>
```

⚠️ 安全设置里若勾了「签名校验」，纯 webhook 不够（见附录）。**建议先别勾**，或复用一个已知没开签名的群机器人。

---

## Step 2 — 决定发送方式（curl vs python3）

`after_script` 在**该 job 的镜像**里执行。选发送工具：

- **shell runner / 镜像里有 curl**（如 `<agent-service-repo>` 的 `inner-*-java` tag）→ 用 `curl`。
- **镜像是 `python:*-slim` / `node:*` 等，默认无 curl** → 用 `python3` 的 `urllib`（标准库，零依赖，slim 镜像也一定有 python3）。别赌 curl 在不在。

飞书 text 消息 payload：

```json
{"msg_type":"text","content":{"text":"第一行\n第二行"}}
```

（想要彩色卡片/按钮换 `msg_type: "interactive"`，见附录。）

---

## Step 3 — 写 `after_script`（按结构二选一）

### 情形 A：目标 job 就在本仓 `.gitlab-ci.yml` 里

直接给它加 `after_script`。最简单。

### 情形 B：目标 job 来自共享模板（本仓 include 了它）—— 用同名 job 合并

**不要重写**模板的 job。只需在本仓再定义一个**同名** job，GitLab 会把「模板的」和「本仓的」
按 key **深合并**：模板提供 `script/stage/rules`，你只补 `after_script`（模板通常没有 `after_script`，
所以是**纯新增、零覆盖**）。

> 🔴 **头号坑（父子流水线必看）**：如果本仓是父子流水线、模板靠**条件 include**（如
> `if inputs.BUSINESS != ""` 才引入 `web-ci.yml`），那么**不能**把同名 job 的覆盖直接写进主
> `.gitlab-ci.yml`。因为主文件的 job **无条件存在**，在「没 include 模板」的父流水线里，它就成了
> 一个只有 `after_script`、缺 `script` 的**孤立非法 job**，导致流水线**连创建都失败**：
>
> ```
> jobs <job> config should implement the script:, run:, or trigger: keyword
> ```
>
> （GitLab 是「先合并所有 include，再校验最终结果」。父流水线没模板可合并 → 缺 script → 挂。）
>
> ✅ **正解**：把覆盖单独放一个本地文件，用**和模板相同的条件** include 进来——保证「有模板的
> 地方才有覆盖」，两者同进同出。

**主 `.gitlab-ci.yml` 的 include 段**（新增最后一条）：

```yaml
include:
  - project: '<group>/<ci-group>/<fe-ci-templates>'
    ref: 'master'
    file: 'web-ci.yml'
    rules:
      - if: '"$[[ inputs.BUSINESS ]]" != ""'       # 模板：仅子流水线
  # 通知覆盖：跟模板同条件，只在子流水线生效，父流水线不引入避免非法 job
  - local: '.gitlab/ci/webhook-notify.yml'
    rules:
      - if: '"$[[ inputs.BUSINESS ]]" != ""'
```

**`.gitlab/ci/webhook-notify.yml`（python 版，适合 `python:*-slim` 镜像）**：

```yaml
# 与模板同名 deploy 合并：模板提供 script，这里纯新增 after_script（零覆盖）。
# 本文件只被子流水线 include（见主 .gitlab-ci.yml 的条件），避免父流水线出现缺 script 的非法 job。
deploy:
  variables:
    # 首选：在 GitLab CI/CD Variables 配置 FEISHU_WEBHOOK_URL（masked）后删掉这行。
    # 无权限时的降级：直接硬编码 webhook（见 Step 4 的取舍）。占位符务必替换。
    FEISHU_WEBHOOK_URL: "https://open.feishu.cn/open-apis/bot/v2/hook/<TOKEN>"
  after_script:
    - |
      if [ -z "$FEISHU_WEBHOOK_URL" ]; then
        echo "未配置 FEISHU_WEBHOOK_URL，跳过通知"
        exit 0
      fi
      if [ "$CI_JOB_STATUS" = "success" ]; then
        export FS_TITLE="✅ 部署成功"
      else
        export FS_TITLE="❌ 部署失败"
      fi
      export FS_DATE="$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M')"
      python3 -c '
      import json, os, urllib.request
      lines = [
          os.environ.get("FS_TITLE", ""),
          "📅 日期： " + os.environ.get("FS_DATE", ""),
          "🌱 分支： " + os.environ.get("CI_COMMIT_REF_NAME", ""),
          "🚩 环境： " + (os.environ.get("ENV") or "unknown"),
          "📁 项目： " + os.environ.get("CI_PROJECT_NAME", ""),
          "🌐 地址： " + (os.environ.get("WEB_URL") or "-"),
          "👤 触发人： " + os.environ.get("GITLAB_USER_NAME", ""),
          "🔗 Pipeline： " + os.environ.get("CI_PIPELINE_URL", ""),
      ]
      payload = {"msg_type": "text", "content": {"text": "\n".join(lines)}}
      req = urllib.request.Request(os.environ["FEISHU_WEBHOOK_URL"], data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
      try:
          urllib.request.urlopen(req, timeout=10).read()
      except Exception as e:
          print("通知发送失败:", e)
      ' || true
```

**curl 版（shell runner / 有 curl 的镜像）**——写进 job 的 `after_script`：

```yaml
after_script:
  - |
    [ -z "$FEISHU_WEBHOOK_URL" ] && { echo "无 webhook，跳过"; exit 0; }
    if [ "$CI_JOB_STATUS" = "success" ]; then TITLE="✅ 部署成功"; else TITLE="❌ 部署失败"; fi
    TEXT="${TITLE}\n📅 $(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M')\n🌱 ${CI_COMMIT_REF_NAME}\n📁 ${CI_PROJECT_NAME}\n👤 ${GITLAB_USER_NAME}\n🔗 ${CI_PIPELINE_URL}"
    curl -sS -X POST "$FEISHU_WEBHOOK_URL" -H "Content-Type: application/json" \
      -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"${TEXT}\"}}" || true
```

**两版共同的健壮性设计**（都别省）：
- `[ -z "$FEISHU_WEBHOOK_URL" ]` 未配则静默跳过 → 变量没配也不报错，可安全先合入。
- `|| true` 兜底 → **通知失败绝不把 job 变红**（`after_script` 本身失败 GitLab 也会忽略，双保险）。
- `$CI_JOB_STATUS` 判成败 → 一处 `after_script` 同时覆盖成功/失败两种通知，不用拆两个 job。
- 时间用 `TZ='Asia/Shanghai'`，否则 runner 多半是 UTC。

---

## Step 4 — webhook 凭据：CI/CD 变量（首选）vs 硬编码（降级）

| 方式 | 何时用 | 取舍 |
|---|---|---|
| **CI/CD Variable**（首选） | 有 Maintainer 权限 | `Settings → CI/CD → Variables`，Key=`FEISHU_WEBHOOK_URL`，勾 **Masked**。可配在**项目**或**上级 group**（配在 group 则全组项目自动继承）。符合「凭据不进 git」。 |
| **硬编码进 YAML**（降级） | 无 Maintainer、只能 push | 写进 job 的 `variables:`。代价：webhook 进了仓库（飞书提示勿公开；内部仓风险=最多被刷群消息）。 |

**变量优先级（关键）**：GitLab 项目/组的 CI/CD Variables **高于** YAML 里的 `variables:`。
所以即使先硬编码，日后有人在后台配了同名变量，会**自动覆盖**硬编码值——**迁移零改码**，
只删 YAML 里那行 `variables` 即可。保留 `$FEISHU_WEBHOOK_URL` 这层间接就是为了这条迁移路径。

> 本 skill 仓库约定禁止硬编码 secret：示例里 webhook 一律用 `<TOKEN>` 占位符，真实值只写进
> **业务仓**（且优先走变量）。

---

## Step 5 — 本地验证（推之前先跑通逻辑）

把 `after_script` 的脚本抠出来，在本地/WSL 干跑两条路径：

```bash
# 用例1：未配 webhook → 应打印「跳过」并 exit 0
env -i CI_JOB_STATUS=success bash after.sh

# 用例2：配假 webhook → 应「发送失败」但被 || true 吞掉，exit 0（不拖垮 job）
env -i CI_JOB_STATUS=failed FEISHU_WEBHOOK_URL='http://127.0.0.1:9/x' \
  CI_COMMIT_REF_NAME=release/v1 ENV=test CI_PROJECT_NAME=demo \
  GITLAB_USER_NAME=me CI_PIPELINE_URL=https://x bash after.sh; echo "exit=$?"
```

想验真实消息内容，起个本地 HTTP 接收端抓 payload，或**直接发一条标注「测试」的消息到群**
（发前跟用户确认，别无声刷群）。飞书返回 `{"code":0,"msg":"success"}` 即投递成功。

---

## Step 6 — 触发时机（最容易误解，务必讲清）

1. **必须先 push**：GitLab 跑流水线读的是**仓库里**的 `.gitlab-ci.yml`，不是本地。只 commit 不 push 不生效。
2. **必须是「新」流水线**：通知挂在 `after_script`，只有该 job **真正执行**才发。
   > ⚠️ **重跑旧流水线没用**：GitLab 用的是那条流水线对应 commit 的配置。retry 旧 job 用的还是旧 YAML。
   > **必须是配置合入分支之后新建的流水线**。
3. 自动部署环境（test/dev/preview）推代码即自动发；`when: manual` 的环境（常见 production）手点部署后才发。
4. 父子流水线：每个业务方/租户是独立子流水线、独立 deploy，会**各发一条**（用 `$BUSINESS` 等区分）。

---

## 踩坑清单（每条都来自实战）

**#1【头号坑】父子流水线 + 条件 include 下，同名 job 覆盖不能放主文件。**
主 `.gitlab-ci.yml` 的 job 无条件存在；在「没 include 模板」的那半边流水线（如父流水线
`BUSINESS==""`）里，只有 `after_script`、缺 `script` 的孤立 job → 报
`jobs <job> config should implement the script:, run:, or trigger: keyword` → **整条流水线连创建都失败**。
→ 把覆盖挪进独立本地文件，用**和模板相同的条件** `include: local:` 引入。见 Step 3 情形 B。

**#2 `python:*-slim` 等镜像默认无 curl。** `after_script` 用 curl 会「command not found」（虽被
`after_script` 忽略但通知发不出）。→ 这类镜像用 `python3 -c` + `urllib`（标准库，一定在）。
先看目标 job 的 `image` / runner 类型再选工具。

**#3 通知失败不能拖垮部署。** 网络抖动、飞书限流、webhook 打错都可能让发送命令非零退出。
→ 结尾 `|| true`；`after_script` 本身失败 GitLab 也会忽略（双保险）。

**#4 webhook 别裸奔进 git（能走变量就走变量）。** 硬编码是无 Maintainer 权限时的降级手段。
优先 CI/CD Variables + Masked；记住**后台变量优先级高于 YAML**，迁移零改码（Step 4）。

**#5 时区。** runner 默认多为 UTC，日期会差 8 小时。→ `TZ='Asia/Shanghai' date ...`。

**#6 飞书签名校验开了就不能纯 POST。** 群机器人若启用签名，body 需带 `timestamp` + `sign`
（HMAC-SHA256）。→ 复用「已在收消息」的群可确认没开；真开了见附录。

**#7 python heredoc / 引号地狱。** 在 YAML 的 `- |` 块里用 `python3 -c '...'` 单引号包多行
python，比 heredoc 稳（heredoc 的结束符受 YAML 缩进影响易翻车）。python 串里 `\n` 在 shell
单引号中是字面量、由 python 解释为换行，正好。JSON 里的双引号不与外层单引号冲突。

**#8 只发成功没发失败，价值减半。** 失败通知往往比成功更需要。用 `$CI_JOB_STATUS` 一处覆盖两种，
别只写成功分支。

---

## 附录

**A. 彩色消息卡片（`msg_type: interactive`）**：把 payload 换成飞书卡片 JSON（header 可设
`template: green/red` 区分成败，含可点按钮跳 Pipeline）。text 版最稳，卡片版更好看，按需升级。

**B. 签名校验版**：飞书签名 = `base64(HMAC-SHA256(key=f"{timestamp}\n{secret}", msg=""))`，
body 加 `"timestamp"` 与 `"sign"` 字段。纯 shell 算 sign 繁琐，建议用 python：
`hmac.new((f"{ts}\n{secret}").encode(), b"", hashlib.sha256).digest()` 再 `base64`。

**C. 换其他 IM**：企业微信/钉钉/Slack 同一套思路（`after_script` + `CI_JOB_STATUS` + POST），
只是 payload schema 不同（企业微信 `{"msgtype":"text","text":{"content":...}}`；Slack `{"text":...}`）。

**D. 常用 GitLab 预定义变量**：`CI_JOB_STATUS` `CI_COMMIT_REF_NAME` `CI_COMMIT_SHORT_SHA`
`CI_PROJECT_NAME` `CI_PIPELINE_URL` `CI_PIPELINE_IID` `GITLAB_USER_NAME`；自定义的如 `ENV` `BUSINESS` `WEB_URL` 视模板而定。

## 与 x-ai-ci-deploy 的关系

- `x-ai-ci-deploy`：把服务**接入 CI**、构建镜像、部署（有的公司模板自带 `notify` 阶段）。
- `x-ai-webhook-message`（本 skill）：给流水线**补/定制通知**，尤其是模板没带通知、或要发到
  指定群、或要在**不改共享模板**的前提下只给本项目加通知的场景。
