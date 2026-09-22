---
name: x-ai-ssh-remote
description: 非交互 SSH 登录远程服务器并跑命令，兼顾密码登录到密钥登录的安全迁移。用户提到连服务器、登录/ssh 到某台机器、帮我连远程主机、测试 SSH 连接、跑一条远程命令、密码登录服务器、sshpass 装不上、把服务器改成密钥登录、禁用密码登录、加固 SSH 时使用。核心解法=本机没 sshpass 又装不上（无 root）时，改用 python3 + paramiko 非交互传密码；凭据全从环境变量读、禁硬编码禁贴聊天。覆盖：连通性自检（/dev/tcp 探端口）、paramiko 跑命令、密钥迁移（生成密钥→幂等植入 authorized_keys→验证）、关闭密码登录的可逆步骤。不负责部署镜像（用 x-ai-server-deploy）、查后端库（用 x-ai-backend-mysql）、查 CLS 日志（用 x-ai-log-cls-trace）。
---

# x-ai-ssh-remote — 非交互 SSH 登录 + 密钥迁移

给一台服务器（IP + 用户 + 端口 + 密码或密钥），稳定地非交互登进去跑命令；
密码登录的机器再引导迁到密钥登录、关掉密码登录。

**红线：凭据只从环境变量读，不写进任何脚本/skill 文件，不回贴到聊天记录。**
密码明文发进对话就已泄露（会话会被缓存），用完提醒 owner 改密码或换密钥。

## 决策：怎么连

| 现状 | 走法 |
|---|---|
| 本机 `~/.ssh/config` 有别名 / 已配免密 | 直接 `ssh 别名`，最省事，不用本 skill 脚本 |
| 有私钥文件 | `SSH_KEY=... scripts/ssh_run.py`，或裸 `ssh -i key user@host` |
| 只有密码，且本机有 `sshpass` | `sshpass -e ssh ...`（`SSHPASS` 走 env，别用 `-p` 上命令行） |
| 只有密码，`sshpass` 缺且无 root 装不上 | **paramiko 兜底**（本仓环境常态）→ `scripts/ssh_run.py` |

自检一条命令看清路子：`which sshpass; python3 -c 'import paramiko'`。
本仓 WSL 环境实测：无 sshpass、不能 `sudo apt`（无终端密码）、但 python3 自带 paramiko。

## 三步用法

### ① 连通性自检（先探端口，再验认证）

```bash
# 端口可达性（VPC 内网 10.x 大概率够不着，公网一般通）
timeout 10 bash -c 'cat </dev/null >/dev/tcp/<HOST>/22' && echo OPEN || echo UNREACHABLE

# 握手 + 认证自检（默认跑 hostname/whoami/uname/uptime）
SSH_HOST=<HOST> SSH_PASS='<密码>' python3 scripts/ssh_run.py --test
```

### ② 跑命令

```bash
# 单条
SSH_HOST=<HOST> SSH_PASS='<密码>' python3 scripts/ssh_run.py 'docker ps'

# 多条，各自独立执行、输出分段、任一非零退出码回传
SSH_HOST=<HOST> SSH_USER=root SSH_KEY=~/.ssh/id_ed25519 \
  python3 scripts/ssh_run.py 'hostname' 'df -h' 'systemctl status nginx'
```

密码含特殊字符（`@ % ) ? .` 等）不用转义——走环境变量不过 shell。

### ③ 迁移到密钥登录（安全整改）

密码登录（尤其 root）是弱项：可被爆破、密码会随聊天/日志泄露。整改两步，**可逆优先**。

**a. 植入公钥并验证**（幂等，重复跑安全）：

```bash
SSH_HOST=<HOST> SSH_PASS='<密码>' python3 scripts/setup_key_login.py
# 本机无密钥会自动生成 ed25519 → 密码会话写入 authorized_keys → 密钥回连验证
```

等价手动：本机 `ssh-keygen -t ed25519` 后 `ssh-copy-id user@host`（本机有 sshpass 时）。

**b. 关掉密码登录**（验证密钥可用后，人工确认再做；**先留一个已登录会话别断**，防锁死）：

```bash
# /etc/ssh/sshd_config
PasswordAuthentication no
PermitRootLogin prohibit-password   # 想彻底禁 root 直登可设 no
# 再 reload（不同发行版择一）
systemctl reload sshd || systemctl reload ssh
```

改完**开新终端**验证密钥能登、密码被拒，确认无误再关旧会话。

### ④ 收尾：把机器登记进 `~/.ssh/config`（强烈推荐）

密钥能登之后，**别每次都手打 `ssh -i ~/.ssh/id_ed25519 root@1.2.3.4`**——登记一个别名，以后 `ssh <别名>` 一个词直连，也不用再走本 skill 的脚本了：

```
# ~/.ssh/config 追加
Host <别名>
    HostName <IP>
    User root
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

团队实践：别名短且语义化，按机器用途命名（如 `<test-host-main>` = 测试环境中间件机、`<test-host-jump>` = 测试环境某服务机），不用 IP 或全名。

配完验证：

```bash
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new <别名> 'whoami; hostname'
```

`setup_key_login.py` 验证通过后会打印一段可直接追加的 Host 块，抄进 `~/.ssh/config` 即可，脚本本身不动这个文件（属于用户级配置，写不写、别名叫什么由人工决定）。

## 踩坑清单

- **sshpass 装不上**：`sudo apt` 报 `a terminal is required`（无密码）或 `dpkg lock`（非 root）——别耗在装 sshpass，直接走 paramiko。
- **密码别上命令行**：`sshpass -p '密码'` / `ssh` 参数会进 `ps` 和 shell history。一律走 env（`SSHPASS` / 本 skill 的 `SSH_PASS`）。
- **网络可达性会变**：内网 VPC 的 10.x 从本机/沙箱够不着（代理 502 或空响应），公网 IP 一般通。先 `/dev/tcp` 探端口，别把连不上当认证失败。
- **首连主机指纹**：脚本用 `AutoAddPolicy` 自动接受，省去交互；生产环境如需校验指纹自行改策略。
- **改 sshd 会锁死自己**：关密码登录/改端口前必须先验证新方式可登，且保留一个活会话兜底。
- **登录 banner 里的失败次数是真实证据**：`ssh` 登录成功后的 banner 常带 `There were N failed login attempts since the last successful login`，公网 IP 的 root 账号这个数字动辄上万——这是"密码登录已被扫描/爆破"的实测证据，不是假设，看到就该把关密码登录的优先级调高。
- **凭据落文件**：脚本零 secret，全 env 读；owner 给的密码用完提醒改掉或换密钥。

## 相关 skill

- 服务器上部署镜像 / 起容器 → `x-ai-server-deploy`
- 查后端库数据 → `x-ai-backend-mysql`（直连，不用 SSH）
- 查 CLS 日志 / traceId 排障 → `x-ai-log-cls-trace`（走 API，不用 SSH）
