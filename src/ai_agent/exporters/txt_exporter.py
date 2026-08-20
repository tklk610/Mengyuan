"""Txt 导出器

将已完成的小说章节导出为 txt 文件
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChapterDraft:
    """章节草稿"""
    chapter: int
    title: str
    draft: str
    word_count: int


def export_to_txt(title: str, completed_chapters: list[dict], output_path: str | None = None) -> str:
    """导出小说为 txt 格式

    Args:
        title: 小说标题
        completed_chapters: 已完成章节列表
        output_path: 输出文件路径（可选）

    Returns:
        导出的文本内容
    """
    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"{title}")
    lines.append(f"{'=' * 60}")
    lines.append("")

    for ch in completed_chapters:
        chapter_num = ch.get("chapter", 0)
        chapter_title = ch.get("title", f"第{chapter_num}章")
        draft = ch.get("draft", "")
        word_count = ch.get("word_count", 0)

        lines.append(f"\n{'─' * 40}")
        lines.append(f"第{chapter_num}章：{chapter_title}")
        lines.append(f"字数：{word_count}")
        lines.append(f"{'─' * 40}")
        lines.append("")
        lines.append(draft)
        lines.append("")

    content = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    return content
