"""Sensitive Word Filter - 内容安全过滤

敏感词检测中间件，对草稿内容进行敏感词检测和过滤。
支持自定义敏感词库和检测规则。
"""
from __future__ import annotations

import re
from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class SensitiveWordResult(NamedTuple):
    """敏感词检测结果"""

    is_clean: bool
    """是否通过检测（无敏感词）"""
    found_words: list[str]
    """检测到的敏感词列表"""
    filtered_text: str
    """过滤后的文本（敏感词替换为星号）"""
    confidence: float
    """检测置信度（0.0-1.0）"""


class SensitiveWordFilter:
    """敏感词过滤器

    支持：
    - 内置基础敏感词库
    - 自定义敏感词库
    - 正则表达式匹配
    - 敏感词替换（星号掩码）
    """

    # 内置基础敏感词库（示例，实际使用时请根据需求扩展）
    DEFAULT_SENSITIVE_WORDS: set[str] = {
        # 政治敏感词（示例）
        "分裂国家",
        "颠覆政权",
        "反动",
        # 色情低俗词（示例）
        "色情",
        "淫秽",
        "赌博",
        # 暴力恐怖词（示例）
        "恐怖主义",
        "暴力",
        "杀人",
        # 其他违规词（示例）
        "毒品",
        "走私",
    }

    def __init__(
        self,
        custom_words: set[str] | None = None,
        use_regex: bool = True,
        mask_char: str = "*",
    ):
        """初始化敏感词过滤器

        Args:
            custom_words: 自定义敏感词集合，为空则仅使用内置词库
            use_regex: 是否启用正则表达式匹配（默认启用）
            mask_char: 敏感词替换字符
        """
        self._words = self.DEFAULT_SENSITIVE_WORDS.copy()
        if custom_words:
            self._words.update(custom_words)
        self._use_regex = use_regex
        self._mask_char = mask_char
        self._regex_pattern: re.Pattern | None = None
        if self._use_regex and self._words:
            # 构建正则表达式模式（忽略大小写）
            escaped_words = [re.escape(word) for word in self._words]
            pattern_str = "|".join(escaped_words)
            self._regex_pattern = re.compile(pattern_str, re.IGNORECASE)

    def add_words(self, words: set[str]) -> None:
        """动态添加敏感词

        Args:
            words: 要添加的敏感词集合
        """
        self._words.update(words)
        if self._words:
            escaped_words = [re.escape(word) for word in self._words]
            pattern_str = "|".join(escaped_words)
            self._regex_pattern = re.compile(pattern_str, re.IGNORECASE)

    def check(self, text: str) -> SensitiveWordResult:
        """检测文本是否包含敏感词

        Args:
            text: 待检测文本

        Returns:
            SensitiveWordResult: 包含检测结果的命名元组
        """
        if not text or not text.strip():
            return SensitiveWordResult(
                is_clean=True,
                found_words=[],
                filtered_text=text or "",
                confidence=1.0,
            )

        found_words: list[str] = []

        # 正则匹配
        if self._regex_pattern:
            matches = self._regex_pattern.findall(text)
            found_words.extend(matches)

        # 精确匹配（针对正则未匹配的情况）
        text_lower = text.lower()
        for word in self._words:
            if word.lower() in text_lower and word not in found_words:
                found_words.append(word)

        # 去重
        found_words = list(set(found_words))

        # 计算置信度
        confidence = 1.0 if not found_words else max(0.5, 1.0 - len(found_words) * 0.1)

        # 过滤敏感词
        filtered_text = self._mask_words(text, found_words)

        return SensitiveWordResult(
            is_clean=len(found_words) == 0,
            found_words=found_words,
            filtered_text=filtered_text,
            confidence=confidence,
        )

    def _mask_words(self, text: str, found_words: list[str]) -> str:
        """将文本中的敏感词替换为星号

        Args:
            text: 原始文本
            found_words: 要替换的敏感词列表

        Returns:
            替换后的文本
        """
        if not found_words:
            return text

        result = text
        for word in found_words:
            # 替换所有出现的敏感词（忽略大小写）
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub(self._mask_char * len(word), result)

        return result

    def filter(self, text: str) -> str:
        """直接获取过滤后的文本

        Args:
            text: 待过滤文本

        Returns:
            过滤后的文本（敏感词替换为星号）
        """
        result = self.check(text)
        return result.filtered_text

    @property
    def word_count(self) -> int:
        """当前敏感词库词数"""
        return len(self._words)


# === 全局单例实例 ===
_filter_instance: SensitiveWordFilter | None = None


def get_filter() -> SensitiveWordFilter:
    """获取全局敏感词过滤器单例

    Returns:
        SensitiveWordFilter 实例
    """
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = SensitiveWordFilter()
    return _filter_instance


def check_sensitive_words(text: str) -> SensitiveWordResult:
    """便捷函数：检测文本敏感词

    Args:
        text: 待检测文本

    Returns:
        SensitiveWordResult: 检测结果
    """
    return get_filter().check(text)


def filter_sensitive_words(text: str) -> str:
    """便捷函数：过滤文本敏感词

    Args:
        text: 待过滤文本

    Returns:
        过滤后的文本
    """
    return get_filter().filter(text)
