#!/usr/bin/env python3
"""统计 Apifox 导出的 OpenAPI(OAS) 接口数 —— 按 URL path 前缀归类（导出无 tag/无目录）。

用法：
  python3 oas_stats.py <oas.txt>                      # 总览：总数 + 一级前缀分布
  python3 oas_stats.py <oas.txt> --prefix /<user-center-db>        # 某前缀计数 + 二级细分
  python3 oas_stats.py <oas.txt> --prefix /<user-center-db> --list # 列出该前缀下全部 method+path

输入文件是 read_project_oas_* 落盘的那份 .txt（合法 OpenAPI 3.1 JSON）。
本团队 WSL/Linux 环境无 jq，故用 Python 标准库。
"""
import json
import sys
import collections

METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def load_paths(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("paths", {}) or {}


def first_seg(p):
    parts = [x for x in p.split("/") if x]
    return "/" + parts[0] if parts else "/(root)"


def nth_seg(p, n):
    parts = [x for x in p.split("/") if x]
    return parts[n] if len(parts) > n else "(直属)"


def count_ops(item):
    """一个 path item 下的操作数。operation 可能是 dict 或 $ref 字符串，均按 method key 计。"""
    if not isinstance(item, dict):
        return 1
    n = sum(1 for k in item if k.lower() in METHODS)
    return n or 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    fpath = sys.argv[1]
    prefix = None
    do_list = "--list" in sys.argv
    if "--prefix" in sys.argv:
        prefix = sys.argv[sys.argv.index("--prefix") + 1]

    paths = load_paths(fpath)
    total = sum(count_ops(v) for v in paths.values())
    print(f"接口操作总数(operations): {total}")
    print(f"路径数(paths): {len(paths)}")

    if not prefix:
        dist = collections.Counter()
        for p in paths:
            dist[first_seg(p)] += 1
        print("\n--- 一级前缀分布（≈ 模块）---")
        for seg, c in dist.most_common():
            print(f"{c:5d}  {seg}")
        print("\n提示：用 --prefix /xxx 细分某模块。")
        return

    sel = [p for p in paths if p.startswith(prefix)]
    sel_ops = sum(count_ops(paths[p]) for p in sel)
    print(f"\n前缀 {prefix} : {len(sel)} 个路径 / {sel_ops} 个操作")

    if do_list:
        print("--- 接口清单 ---")
        for p in sorted(sel):
            item = paths[p]
            ms = (
                ",".join(m.upper() for m in item if m.lower() in METHODS)
                if isinstance(item, dict)
                else "?"
            )
            print(f"  [{ms or '?'}] {p}")
        return

    depth = len([x for x in prefix.split("/") if x])
    sub = collections.Counter()
    for p in sel:
        sub[nth_seg(p, depth)] += 1
    print(f"--- {prefix} 下一级细分 ---")
    for seg, c in sub.most_common():
        print(f"{c:5d}  {prefix}/{seg}")


if __name__ == "__main__":
    main()
