#!/usr/bin/env python3
"""
Harness Engineering — R16 变更留痕检查

> 用途：检查本次变更是否在 .harness/changes/{YYYYMMDD}-{feat}/summary.md 留有变更记录。
> 触发：git pre-commit / CI / `make pre-commit`

═══════════════════════════════════════════════════════════════════════════════
检查规则：
    1. 任何修改的 *.py 文件（超过 50 行）必须有对应的 summary.md
    2. summary.md 必须包含必填段：1.需求描述 / 5.冲突报告 / 7.回滚方案 / 9.Owner
    3. *.md 文档变更可豁免（simplified summary 即可）
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANGES_DIR = PROJECT_ROOT / ".harness" / "changes"

REQUIRED_SECTIONS = [
    "## 1.",  # 需求描述
    "## 5.",  # 冲突报告
    "## 7.",  # 回滚方案
    "## 9.",  # Owner
]

IGNORED_PATTERNS = [
    r"\.mypy_cache/",
    r"__pycache__/",
    r"\.git/",
    r"\.venv/",
    r"docs/",  # 纯文档可豁免
    r"\.harness/changes/",  # changes 目录本身豁免
    r"scripts/check_red_lines\.py",
    r"scripts/check_change_doc\.py",
    r"\.harness/skills/",  # skill 文档豁免
    r"\.harness/wiki/",  # wiki 文档豁免
    r"\.harness/rules/",  # rules 文档豁免（红线条目）
]


def get_staged_files() -> list[Path]:
    """获取 git staged 的文件列表"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return [PROJECT_ROOT / p for p in result.stdout.splitlines() if p.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        # git 命令不存在 / 不是 git 仓库 / 没有 staged 文件，均视为无可检查项
        return []


def get_modified_files() -> list[Path]:
    """获取 git 已修改但未 staged 的文件（兜底）"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        files = []
        for line in result.stdout.splitlines():
            if len(line) > 3:
                path = line[3:].strip()
                if "->" in path:
                    path = path.split("->")[-1].strip()
                files.append(PROJECT_ROOT / path)
        return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def is_ignored(path: Path) -> bool:
    """是否豁免 R16 检查"""
    rel = str(path.relative_to(PROJECT_ROOT))
    return any(re.search(p, rel) for p in IGNORED_PATTERNS)


def is_significant_code(path: Path) -> bool:
    """是否是有意义的代码变更（超过 50 行）"""
    if path.suffix != ".py":
        return False
    try:
        text = path.read_text(encoding="utf-8")
        return text.count("\n") > 50
    except (FileNotFoundError, UnicodeDecodeError):
        return False


def find_change_summary(code_path: Path) -> Path | None:
    """查找与代码文件关联的变更目录"""
    # 约定：.harness/changes/{YYYYMMDD}-{feat-name}/summary.md
    if not CHANGES_DIR.exists():
        return None
    # 取最近修改的 summary.md（简单实现，真实场景可用 git log 关联）
    summaries = sorted(
        CHANGES_DIR.glob("*/summary.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return summaries[0] if summaries else None


def validate_summary(summary: Path) -> list[str]:
    """验证 summary.md 必填段"""
    errors = []
    try:
        text = summary.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError) as e:
        return [f"无法读取 {summary}: {e}"]

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"  - 缺少必填段：{section.rstrip('.')}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="R16 变更留痕检查")
    parser.add_argument(
        "--check-staged",
        action="store_true",
        help="检查 git staged 文件（pre-commit 默认）",
    )
    parser.add_argument(
        "--check-modified",
        action="store_true",
        help="检查 git 已修改但未 staged 的文件",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：警告也算失败",
    )
    args = parser.parse_args()

    # 默认行为
    if not (args.check_staged or args.check_modified):
        args.check_staged = True

    files = get_staged_files() if args.check_staged else []
    files += get_modified_files() if args.check_modified else []

    if not files:
        print("✅ R16: no code changes detected, skip.")
        return 0

    # 筛选需要检查的代码文件
    code_files = [f for f in files if not is_ignored(f) and is_significant_code(f)]

    if not code_files:
        print(f"✅ R16: {len(files)} files checked, no significant code changes require summary.md.")
        return 0

    # 查找关联的 summary.md
    violations = []
    summary = find_change_summary(code_files[0])
    if not summary:
        violations.append(
            f"❌ R16 违规：{len(code_files)} 个代码文件变更，"
            f"但 .harness/changes/ 下找不到任何 summary.md。"
        )
    else:
        errors = validate_summary(summary)
        if errors:
            violations.append(
                f"❌ R16 违规：{summary.relative_to(PROJECT_ROOT)} 必填段缺失：\n"
                + "\n".join(errors)
            )

    if violations:
        print("\n".join(violations))
        print("\n📖 修复指引：")
        print("  1. 在 .harness/changes/ 下新建 {YYYYMMDD}-{feat-name}/ 目录")
        print("  2. 复制 templates/summary.template.md 起一份")
        print("  3. 填齐 1/5/7/9 段")
        return 1

    print(f"✅ R16: {len(code_files)} code changes, summary.md found and valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
