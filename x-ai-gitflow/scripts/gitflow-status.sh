#!/usr/bin/env bash
set -u

if ! repo_root=$(git rev-parse --show-toplevel 2>/dev/null); then
  printf '错误: 当前目录不在 Git 仓库中\n' >&2
  exit 2
fi

git_dir=$(git rev-parse --git-dir)
current_branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || printf 'DETACHED')
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)
remote_default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)

operation='none'
if [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]; then
  operation='rebase'
elif [ -f "$(git rev-parse --git-path MERGE_HEAD)" ]; then
  operation='merge'
elif [ -f "$(git rev-parse --git-path CHERRY_PICK_HEAD)" ]; then
  operation='cherry-pick'
elif [ -f "$(git rev-parse --git-path REVERT_HEAD)" ]; then
  operation='revert'
fi

porcelain=$(git status --porcelain=v1)
if [ -n "$porcelain" ]; then
  worktree_state='dirty'
  change_count=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
else
  worktree_state='clean'
  change_count='0'
fi

printf 'repo_root=%s\n' "$repo_root"
printf 'git_dir=%s\n' "$git_dir"
printf 'branch=%s\n' "$current_branch"
printf 'operation=%s\n' "$operation"
printf 'worktree=%s\n' "$worktree_state"
printf 'changes=%s\n' "$change_count"
printf 'upstream=%s\n' "${upstream:-none}"
printf 'remote_default=%s\n' "${remote_default:-unknown}"

if [ -n "$upstream" ]; then
  counts=$(git rev-list --left-right --count "$upstream...HEAD")
  behind=${counts%%[[:space:]]*}
  ahead=${counts##*[[:space:]]}
  printf 'ahead=%s\n' "$ahead"
  printf 'behind=%s\n' "$behind"
else
  printf 'ahead=unknown\n'
  printf 'behind=unknown\n'
fi

for branch in dev master main; do
  if git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    printf 'remote_branch.%s=present\n' "$branch"
  else
    printf 'remote_branch.%s=absent\n' "$branch"
  fi
done

printf 'worktrees:\n'
git worktree list --porcelain | awk '
  /^worktree / { path = substr($0, 10) }
  /^branch / {
    branch = $0
    sub("^branch refs/heads/", "", branch)
    printf "  - path=%s branch=%s\n", path, branch
  }
  /^detached$/ {
    printf "  - path=%s branch=DETACHED\n", path
  }
'
