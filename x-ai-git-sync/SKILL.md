---
name: x-ai-git-sync
description: 处理本地分支与远端的「分叉（diverged）」——本地和远端各自有对方没有的提交，需要整合。用户提到处理分叉、和远端分叉了、diverged、本地领先 X 落后 Y、git pull 冲突、要不要 rebase 还是 merge、同步远端分支、推不上去（non-fast-forward / rejected）、别人 force push 了我怎么办、整合远端改动 时，主动使用本 skill。覆盖：fetch 后判断领先/落后、比对两边改动文件识别冲突风险、决策 rebase（默认，线性历史）还是 merge、冲突处理与安全回滚（rebase --abort / reflog）、rebase 后用 fast-forward push（不用 force）、何时才需要 --force-with-lease、以及 gitlab-shell 那条无害告警的说明。不负责普通提交（用 ce-commit）、开 PR（用 ce-commit-push-pr）、清理已删除分支（用 ce-clean-gone-branches）。
---

# x-ai-git-sync — 处理本地分支与远端的分叉

**分叉（diverged）**：`git status` 提示 `Your branch and 'origin/xxx' have diverged, and have N and M different commits each`。
意思是从共同基点（merge-base）分开后，**本地有 N 个远端没有的提交，远端有 M 个本地没有的提交**。
直接 `git pull` 会按默认策略乱来（可能生成 merge commit 或报错），所以要先看清楚再决定怎么整合。

核心四步：**摸清现状 → 评估冲突风险 → 选 rebase 还是 merge → 整合并推送**。任何一步出错都能安全回滚。

---

## 第一步：摸清现状（只读，先别动）

跑诊断脚本（推荐），它会一次性打印领先/落后数、两边各自的提交、改动文件、重叠文件：

```bash
bash <skill-dir>/scripts/diverge-status.sh
# 或指定远端分支：bash scripts/diverge-status.sh origin/feat/xxx
```

不用脚本就手动跑这几条（`UP` 替换成上游，如 `origin/feat/sdd-driven-refactor`）：

```bash
git fetch                                          # 先同步远端引用
UP=$(git rev-parse --abbrev-ref @{u})              # 当前分支的上游
git log --oneline $UP..HEAD                         # 本地独有的提交（rebase 时会被重放的就是这些）
git log --oneline HEAD..$UP                         # 远端独有的提交
git merge-base HEAD $UP                             # 共同基点
```

> **gitlab-shell 告警是无害的**：`fetch`/`push` 时若看到
> `gitlab-shell: Unable to configure logging: ... permission denied, Unix syslog delivery error`，
> 这是服务端 hook 写日志的权限告警，**不影响操作结果**，照常看 `Everything up-to-date` / 推送成功即可。

---

## 第二步：评估冲突风险

关键判断：**两边改动的文件有没有重叠**。重叠越少，rebase/merge 越可能自动完成、零冲突。

```bash
MB=$(git merge-base HEAD $UP)
comm -12 <(git diff --name-only $MB..HEAD | sort) <(git diff --name-only $MB..$UP | sort)
```

- **输出为空** → 两边改的是不同文件，几乎必然零冲突，放心 rebase。
- **有重叠文件** → 这些文件**可能**冲突（也可能 git 按行自动合并掉）。先 `git diff $MB..HEAD -- <file>` 和 `git diff $MB..$UP -- <file>` 看两边各自怎么改的，心里有数；真冲突了按第四步处理。

---

## 第三步：选 rebase 还是 merge

**默认选 rebase**（团队用 feature branch 工作流，要线性历史，blame/log 干净）。判断依据是「本地独有的那 N 个提交，有没有已经被别人拿走」：

| 情况 | 选择 | 原因 |
|---|---|---|
| 本地独有提交**从没推到过远端**（最常见的分叉就是这样） | **rebase** | 重写的是只有你自己有的提交，安全，且能得到线性历史 |
| 本地独有提交**曾经推上去过**，别人可能已经基于它工作 | **merge** | rebase 会改写已发布的提交 hash，破坏别人的历史 |
| 远端是被人 **force push** 过的，你要丢掉本地某些重放 | rebase（配合 `--onto` 或交互） | 见下方「别人 force push 了」 |
| 分支是多人高频协作的长期分支、且不在乎线性 | merge | 省去反复 rebase 的摩擦 |

判断「本地提交是否被推过」的快速办法：`git log --oneline $UP..HEAD` 列出的提交，如果都是你刚写、还没 `git push` 过的，就放心 rebase。

---

## 第四步：整合并推送

### 方案 A：rebase（默认）

```bash
git rebase $UP                  # 把本地独有提交逐个重放到远端最新提交之上
```

- **成功**：`Successfully rebased and updated`。此时本地 = 远端最新 + 你的 N 个提交，历史是线性的。
- **遇到冲突**：git 会停下并标出冲突文件。
  ```bash
  git status                    # 看哪些文件冲突
  # 手动编辑解决 <<<<<<< ======= >>>>>>> 标记
  git add <已解决的文件>
  git rebase --continue         # 继续重放下一个提交
  ```
  逐个提交解决直到完成。**任何时候想放弃、回到 rebase 前的原状**：
  ```bash
  git rebase --abort            # 100% 安全地退回，什么都没改变
  ```

rebase 完成后，远端 tip 已是新 HEAD 的祖先，所以推送是 **fast-forward，普通 push 即可，不需要 force**：

```bash
git push                        # 正常推送，不要加 --force
git rev-parse HEAD @{u}         # 两行 hash 应一致 → 同步完成
```

> 如果 `git push` 报 `rejected / non-fast-forward`，说明在你 rebase 期间远端**又有新提交**了。
> 重新 `git fetch` 再 `git rebase $UP` 一次即可，**不要**用 `--force` 去硬推覆盖别人的提交。

### 方案 B：merge

```bash
git merge $UP                   # 生成一个 merge commit 整合两边
# 冲突则：解决 → git add → git commit（或 git merge --continue）
# 想放弃：git merge --abort
git push
```

---

## 特殊情况：别人 force push 了远端

现象：你没改本地，但 `git fetch` 后突然「落后」很多、或 rebase 时出现你认不出的提交。说明有人对远端做了 `git push --force`，远端历史被改写了。

1. 先确认远端现在长啥样：`git log --oneline $UP -15`，和你本地对比。
2. 如果你本地只有自己几个新提交，想把它们挪到远端新历史之上：
   ```bash
   git rebase --onto $UP <你和远端原来的旧基点> HEAD
   ```
   不确定旧基点时，用 `git reflog` 找 force push 之前的远端 hash。
3. **只有在你确认要用本地版本覆盖远端、且和协作者沟通过**之后，才用：
   ```bash
   git push --force-with-lease   # 比 --force 安全：若远端在你预期之外又变了会拒绝
   ```
   **永远优先 `--force-with-lease` 而不是 `--force`**，前者能防止盲覆盖别人刚推的提交。

---

## 安全回滚总表（操作前不慌）

| 我在做什么 | 想撤销 | 命令 |
|---|---|---|
| rebase 进行中 | 退回 rebase 前 | `git rebase --abort` |
| merge 进行中 | 退回 merge 前 | `git merge --abort` |
| rebase/merge 已完成但想反悔 | 找到操作前的 HEAD | `git reflog` 找到旧 hash → `git reset --hard <hash>` |
| 误删了提交 | 几乎都能找回 | `git reflog`（90 天内的 HEAD 移动都有记录） |

只要**还没 force push 到远端**，本地几乎任何 rebase/merge 都能靠 reflog 完整恢复——这就是默认敢用 rebase 的底气。

---

## 一句话决策树

> 分叉了 → `fetch` 看清两边提交 → 比对改动文件估冲突 → 本地提交没被别人拿走就 **rebase**（默认），否则 **merge** → 解决冲突 or `--abort` 回滚 → rebase 后**普通 push（不 force）**，被拒就再 fetch+rebase 一次。
