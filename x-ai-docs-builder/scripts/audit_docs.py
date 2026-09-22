#!/usr/bin/env python3
"""Read-only audit for a repository's Markdown documentation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import unquote

LINK_RE = re.compile(
    r"(?<![\w`])!?\[[^\]\n]*]\(([^()\n]*(?:\([^()\n]*\)[^()\n]*)*)\)"
)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$")
VALID_ISSUE_TYPES = {"decision", "todo", "review-finding"}
VALID_ISSUE_STATUSES = {"open", "decided", "planned", "done", "superseded"}
LEGACY_DIRS = {
    "todos": "issues/ + type: todo",
    "open-issues": "issues/ + type: decision",
    "reviews": "issues/ + type: review-finding",
    "residual-review-findings": "issues/ + type: review-finding",
    "poc": "research/",
    "spikes": "research/",
}
CORE_DIRS = {
    "brainstorms",
    "research",
    "sdd",
    "plans",
    "guides",
    "runbooks",
    "issues",
    "solutions",
}
CONFIG_NAME = ".docs-audit.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Markdown links, indexes, metadata, and document reachability."
    )
    parser.add_argument("repo", nargs="?", default=".", help="Repository root (default: .)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero for warnings as well as errors",
    )
    parser.add_argument(
        "--baseline",
        help="Prior --json output; report and fail only on findings not in the baseline",
    )
    return parser.parse_args()


def add_finding(
    findings: list[dict[str, str]],
    severity: str,
    code: str,
    path: Path,
    message: str,
    root: Path,
) -> None:
    try:
        display_path = path.relative_to(root).as_posix()
    except ValueError:
        display_path = str(path)
    findings.append(
        {
            "severity": severity,
            "code": code,
            "path": display_path,
            "message": message,
        }
    )


def markdown_files(root: Path) -> list[Path]:
    files = [path for path in root.glob("*.md") if path.is_file()]
    docs = root / "docs"
    if docs.is_dir():
        files.extend(path for path in docs.rglob("*.md") if path.is_file())
    return sorted(set(path.resolve() for path in files))


def read_text(path: Path, findings: list[dict[str, str]], root: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        add_finding(
            findings,
            "error",
            "markdown-not-utf8",
            path,
            "Markdown 文件不是 UTF-8 编码",
            root,
        )
    except OSError as exc:
        add_finding(
            findings,
            "error",
            "markdown-unreadable",
            path,
            f"无法读取 Markdown 文件: {exc}",
            root,
        )
    return ""


def load_config(root: Path, findings: list[dict[str, str]]) -> dict[str, Any]:
    path = root / CONFIG_NAME
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        add_finding(
            findings,
            "error",
            "invalid-audit-config",
            path,
            f"无法读取 {CONFIG_NAME}: {exc}",
            root,
        )
        return {}
    if not isinstance(value, dict):
        add_finding(
            findings,
            "error",
            "invalid-audit-config",
            path,
            f"{CONFIG_NAME} 顶层必须是 JSON object",
            root,
        )
        return {}
    return value


def string_list(
    config: dict[str, Any],
    key: str,
    root: Path,
    findings: list[dict[str, str]],
) -> list[str]:
    value = config.get(key, [])
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    add_finding(
        findings,
        "error",
        "invalid-audit-config",
        root / CONFIG_NAME,
        f"{key} 必须是字符串数组",
        root,
    )
    return []


def finding_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("severity", "")),
        str(item.get("code", "")),
        str(item.get("path", "")),
        str(item.get("message", "")),
    )


def load_baseline(
    value: str | None,
    root: Path,
    findings: list[dict[str, str]],
) -> set[tuple[str, str, str, str]]:
    if value is None:
        return set()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("findings") if isinstance(payload, dict) else payload
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            raise ValueError("baseline 必须是审计 JSON object 或 findings 数组")
        return {finding_key(item) for item in items}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        add_finding(
            findings,
            "error",
            "invalid-audit-baseline",
            path,
            f"无法读取审计基线: {exc}",
            root,
        )
        return set()


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        field = FIELD_RE.match(line)
        if not field:
            continue
        value = field.group(2).strip().strip("\"'")
        fields[field.group(1)] = value
    return fields


def clean_link(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    elif " " in target:
        target = target.split(" ", 1)[0]
    target = unquote(target)
    lowered = target.lower()
    if (
        not target
        or target.startswith("#")
        or target.startswith("/")
        or lowered.startswith(("http://", "https://", "mailto:", "tel:", "data:"))
    ):
        return None
    return target.split("#", 1)[0].split("?", 1)[0] or None


def normalize_target(candidate: Path) -> Path:
    if candidate.is_dir():
        readme = candidate / "README.md"
        if readme.is_file():
            return readme.resolve()
    return candidate


def resolve_markdown_target(root: Path, source: Path, target: str) -> Path:
    relative_candidate = normalize_target((source.parent / target).resolve())
    if relative_candidate.exists() or target.startswith("../"):
        return relative_candidate

    # A substantial amount of existing project documentation uses repository-root
    # paths such as docs/... and src/... inside Markdown links. Accept that legacy
    # convention as a fallback while still preferring standard file-relative links.
    root_candidate = normalize_target((root / target).resolve())
    if root_candidate.exists():
        return root_candidate
    return relative_candidate


def audit_links(
    root: Path,
    files: list[Path],
    texts: dict[Path, str],
    findings: list[dict[str, str]],
) -> dict[Path, set[Path]]:
    graph: dict[Path, set[Path]] = {path: set() for path in files}
    known = set(files)
    for source in files:
        for raw_target in LINK_RE.findall(texts[source]):
            target = clean_link(raw_target)
            if target is None:
                continue
            resolved = resolve_markdown_target(root, source, target)
            if not resolved.exists():
                add_finding(
                    findings,
                    "error",
                    "broken-relative-link",
                    source,
                    f"相对链接不存在: {raw_target}",
                    root,
                )
                continue
            if resolved in known:
                graph[source].add(resolved)
    return graph


def audit_indexes(root: Path, docs: Path, findings: list[dict[str, str]]) -> None:
    if not docs.is_dir():
        return
    docs_index = docs / "README.md"
    if not docs_index.is_file():
        add_finding(
            findings,
            "error",
            "missing-docs-index",
            docs,
            "docs/ 存在但缺少 docs/README.md",
            root,
        )
    for name in sorted(CORE_DIRS):
        directory = docs / name
        if not directory.is_dir():
            continue
        direct_docs = [path for path in directory.glob("*.md") if path.name != "README.md"]
        child_dirs = [path for path in directory.iterdir() if path.is_dir()]
        if (len(direct_docs) >= 2 or child_dirs) and not (directory / "README.md").is_file():
            add_finding(
                findings,
                "warning",
                "missing-section-index",
                directory,
                "专题目录包含多篇文档或子目录，但缺少 README.md 索引",
                root,
            )


def audit_legacy_dirs(
    root: Path,
    docs: Path,
    findings: list[dict[str, str]],
    accepted: set[str],
) -> None:
    if not docs.is_dir():
        return
    for name, replacement in LEGACY_DIRS.items():
        if name in accepted:
            continue
        directory = docs / name
        if directory.is_dir():
            add_finding(
                findings,
                "warning",
                "legacy-docs-directory",
                directory,
                f"历史目录仍在使用；新内容建议映射到 {replacement}",
                root,
            )


def audit_metadata(
    root: Path,
    docs: Path,
    files: list[Path],
    texts: dict[Path, str],
    findings: list[dict[str, str]],
) -> None:
    seen_ids: dict[str, Path] = {}
    for path in files:
        fields = parse_frontmatter(texts[path])
        doc_id = fields.get("id")
        if doc_id:
            previous = seen_ids.get(doc_id)
            if previous is not None:
                add_finding(
                    findings,
                    "error",
                    "duplicate-document-id",
                    path,
                    f"文档 ID {doc_id!r} 已在 {previous.relative_to(root).as_posix()} 使用",
                    root,
                )
            else:
                seen_ids[doc_id] = path

    issues = docs / "issues"
    if not issues.is_dir():
        return
    for path in sorted(issues.rglob("*.md")):
        if path.name == "README.md":
            continue
        fields = parse_frontmatter(texts.get(path.resolve(), read_text(path, findings, root)))
        for required in ("id", "type", "status"):
            if not fields.get(required):
                add_finding(
                    findings,
                    "error",
                    "missing-issue-metadata",
                    path,
                    f"issue 缺少 frontmatter 字段: {required}",
                    root,
                )
        issue_type = fields.get("type")
        if issue_type and issue_type not in VALID_ISSUE_TYPES:
            add_finding(
                findings,
                "error",
                "invalid-issue-type",
                path,
                f"非法 issue type: {issue_type}",
                root,
            )
        status = fields.get("status")
        if status and status not in VALID_ISSUE_STATUSES:
            add_finding(
                findings,
                "error",
                "invalid-issue-status",
                path,
                f"非法 issue status: {status}",
                root,
            )


def audit_orphans(
    root: Path,
    docs: Path,
    files: list[Path],
    graph: dict[Path, set[Path]],
    findings: list[dict[str, str]],
    configured_entries: list[str],
    excludes: list[str],
) -> None:
    if not docs.is_dir():
        return
    entries = [
        candidate.resolve()
        for candidate in (root / "README.md", docs / "README.md")
        if candidate.is_file()
    ]
    for configured in configured_entries:
        candidate = (root / configured).resolve()
        if candidate.is_file() and candidate in graph:
            entries.append(candidate)
        else:
            add_finding(
                findings,
                "error",
                "invalid-audit-entrypoint",
                root / configured,
                "配置的文档入口不存在或不是已扫描的 Markdown 文件",
                root,
            )
    if not entries:
        return
    reachable: set[Path] = set(entries)
    queue: deque[Path] = deque(entries)
    while queue:
        current = queue.popleft()
        for target in graph.get(current, set()):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    for path in files:
        if path == (docs / "README.md").resolve() or docs not in path.parents:
            continue
        relative = path.relative_to(root)
        if any(relative.match(pattern) for pattern in excludes):
            continue
        if path not in reachable:
            add_finding(
                findings,
                "warning",
                "orphan-document",
                path,
                "未从根 README、docs/README 或其可达文档链接到",
                root,
            )


def render_text(
    root: Path,
    findings: list[dict[str, str]],
    baseline_count: int,
) -> None:
    if not findings:
        suffix = f"; {baseline_count} baseline finding(s)" if baseline_count else ""
        print(f"docs audit: clean ({root}){suffix}")
        return
    for finding in findings:
        print(
            f"{finding['severity'].upper()} "
            f"[{finding['code']}] {finding['path']}: {finding['message']}"
        )
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    print(
        f"docs audit: {errors} new error(s), {warnings} new warning(s), "
        f"{baseline_count} baseline finding(s)"
    )


def main() -> int:
    args = parse_args()
    root = Path(args.repo).expanduser().resolve()
    if not root.is_dir():
        print(f"repository path is not a directory: {root}", file=sys.stderr)
        return 2

    findings: list[dict[str, str]] = []
    docs = root / "docs"
    config = load_config(root, findings)
    accepted_legacy_dirs = set(
        string_list(config, "accepted_legacy_dirs", root, findings)
    )
    configured_entries = string_list(config, "entrypoints", root, findings)
    orphan_excludes = string_list(config, "orphan_excludes", root, findings)
    files = markdown_files(root)
    texts = {path: read_text(path, findings, root) for path in files}

    graph = audit_links(root, files, texts, findings)
    audit_indexes(root, docs, findings)
    audit_legacy_dirs(root, docs, findings, accepted_legacy_dirs)
    audit_metadata(root, docs, files, texts, findings)
    audit_orphans(
        root,
        docs,
        files,
        graph,
        findings,
        configured_entries,
        orphan_excludes,
    )
    findings.sort(key=lambda item: (item["severity"], item["path"], item["code"]))
    baseline_keys = load_baseline(args.baseline, root, findings)
    baseline_findings = [
        item for item in findings if finding_key(item) in baseline_keys
    ]
    active_findings = [
        item for item in findings if finding_key(item) not in baseline_keys
    ]

    if args.as_json:
        payload: dict[str, Any] = {
            "repository": str(root),
            "summary": {
                "errors": sum(item["severity"] == "error" for item in active_findings),
                "warnings": sum(
                    item["severity"] == "warning" for item in active_findings
                ),
                "baseline": len(baseline_findings),
            },
            "findings": active_findings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        render_text(root, active_findings, len(baseline_findings))

    has_errors = any(item["severity"] == "error" for item in active_findings)
    has_warnings = any(item["severity"] == "warning" for item in active_findings)
    return 1 if has_errors or (args.strict and has_warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
