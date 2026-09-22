#!/usr/bin/env bash
# diverge-status.sh — 一次性打印当前分支与远端的分叉全貌（只读，不改动任何东西）
# 用法:
#   bash diverge-status.sh                 # 用当前分支的上游 @{u}
#   bash diverge-status.sh origin/feat/xxx # 指定要对比的远端分支
set -euo pipefail

echo "==> git fetch（同步远端引用）"
git fetch 2>&1 | grep -v 'gitlab-shell: Unable to configure logging' || true

# 确定上游引用
if [ "${1:-}" != "" ]; then
  UP="$1"
else
  UP="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
fi
if [ -z "${UP:-}" ]; then
  echo "✗ 当前分支没有设置上游，且未传入远端分支参数。"
  echo "  请改用: bash diverge-status.sh origin/<branch>"
  exit 1
fi

LOCAL="$(git rev-parse --abbrev-ref HEAD)"
MB="$(git merge-base HEAD "$UP")"
AHEAD="$(git rev-list --count "$UP"..HEAD)"
BEHIND="$(git rev-list --count HEAD.."$UP")"

echo ""
echo "本地分支 : $LOCAL"
echo "对比上游 : $UP"
echo "共同基点 : $MB"
echo "领先(本地独有): $AHEAD 个提交   落后(远端独有): $BEHIND 个提交"

if [ "$AHEAD" = "0" ] && [ "$BEHIND" = "0" ]; then
  echo ""
  echo "✓ 已同步，没有分叉。"
  exit 0
fi
if [ "$BEHIND" = "0" ]; then
  echo ""
  echo "✓ 仅本地领先（未分叉），直接 git push 即可。"
fi
if [ "$AHEAD" = "0" ]; then
  echo ""
  echo "✓ 仅本地落后（未分叉），直接 git pull --ff-only 即可。"
fi

echo ""
echo "=== 本地独有提交（rebase 时会被重放的就是这些）==="
git log --oneline "$UP"..HEAD || true
echo ""
echo "=== 远端独有提交 ==="
git log --oneline HEAD.."$UP" || true

echo ""
echo "=== 改动文件重叠（潜在冲突点；为空=几乎零冲突）==="
OVERLAP="$(comm -12 \
  <(git diff --name-only "$MB"..HEAD | sort) \
  <(git diff --name-only "$MB".."$UP" | sort) || true)"
if [ -z "$OVERLAP" ]; then
  echo "（无重叠 — 两边改的是不同文件）"
else
  echo "$OVERLAP"
  echo ""
  echo "↑ 这些文件两边都改过，rebase/merge 时可能冲突。"
  echo "  逐个看两边改法: git diff $MB..HEAD -- <file> / git diff $MB..$UP -- <file>"
fi

echo ""
echo "=== 建议 ==="
if [ "$AHEAD" != "0" ] && [ "$BEHIND" != "0" ]; then
  echo "已分叉。本地独有提交若从未推送过 → 默认 rebase:"
  echo "    git rebase $UP   →  解决冲突或 git rebase --abort  →  git push（不加 force）"
  echo "本地独有提交若已被他人拿走 → 改用 merge: git merge $UP"
fi
