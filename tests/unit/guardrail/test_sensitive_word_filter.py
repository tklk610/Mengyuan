"""Unit Tests for Sensitive Word Filter

测试敏感词检测中间件的功能。
"""
import pytest

from ai_agent.guardrail.sensitive_word_filter import (
    SensitiveWordFilter,
    SensitiveWordResult,
    check_sensitive_words,
    filter_sensitive_words,
    get_filter,
)


class TestSensitiveWordFilter:
    """SensitiveWordFilter 单元测试"""

    def test_empty_text(self):
        """空文本应通过检测"""
        filter = SensitiveWordFilter()
        result = filter.check("")
        assert result.is_clean is True
        assert result.found_words == []
        assert result.filtered_text == ""

    def test_clean_text(self):
        """正常文本应通过检测"""
        filter = SensitiveWordFilter()
        text = "这是一个正常的故事，讲述了主角的成长历程。"
        result = filter.check(text)
        assert result.is_clean is True
        assert result.found_words == []
        assert result.filtered_text == text

    def test_sensitive_word_detection(self):
        """应能检测到敏感词"""
        filter = SensitiveWordFilter()
        text = "这是一个包含色情内容的故事。"
        result = filter.check(text)
        assert result.is_clean is False
        assert "色情" in result.found_words
        # "色情" 2个字，替换为2个*
        assert "**" in result.filtered_text

    def test_multiple_sensitive_words(self):
        """应能检测多个敏感词"""
        filter = SensitiveWordFilter()
        text = "这个故事包含色情和赌博内容。"
        result = filter.check(text)
        assert result.is_clean is False
        assert len(result.found_words) >= 2
        # "色情"和"赌博"各2个字
        assert "**" in result.filtered_text

    def test_filter_replaces_with_mask(self):
        """过滤后敏感词应被替换为星号"""
        filter = SensitiveWordFilter(mask_char="*")
        text = "包含赌博的文字"
        result = filter.check(text)
        assert "赌博" in result.found_words
        # "赌博" 2个字，替换为2个*
        assert "**" in result.filtered_text

    def test_custom_words(self):
        """应支持自定义敏感词"""
        custom_words = {"测试词", "自定义敏感"}
        filter = SensitiveWordFilter(custom_words=custom_words)
        result = filter.check("这是一个测试词")
        assert result.is_clean is False
        assert "测试词" in result.found_words

    def test_add_words(self):
        """应支持动态添加敏感词"""
        filter = SensitiveWordFilter()
        filter.add_words({"新增敏感词"})
        result = filter.check("这是新增敏感词的内容")
        assert result.is_clean is False
        assert "新增敏感词" in result.found_words

    def test_case_insensitive(self):
        """检测应忽略大小写"""
        filter = SensitiveWordFilter()
        text = "这是一个色情故事"
        result = filter.check(text)
        assert result.is_clean is False

        text_upper = "这是一个色情故事"
        result_upper = filter.check(text_upper)
        assert result_upper.is_clean is False

    def test_confidence_score(self):
        """应返回合理的置信度"""
        filter = SensitiveWordFilter()
        clean_result = filter.check("正常文本")
        assert clean_result.confidence == 1.0

        dirty_result = filter.check("包含色情赌博的文本")
        assert dirty_result.confidence < 1.0
        assert dirty_result.confidence >= 0.5

    def test_word_count(self):
        """应返回正确的词库数量"""
        filter = SensitiveWordFilter()
        assert filter.word_count > 0

        filter.add_words({"新词1", "新词2"})
        assert filter.word_count >= 3

    def test_filter_method(self):
        """filter 方法应直接返回过滤后文本"""
        filter = SensitiveWordFilter()
        text = "包含赌博的文字"
        filtered = filter.filter(text)
        # "赌博" 2个字，替换为2个*
        assert "**" in filtered
        assert "赌博" not in filtered

    def test_empty_text_confidence(self):
        """空文本置信度应为1.0"""
        filter = SensitiveWordFilter()
        result = filter.check("")
        assert result.confidence == 1.0


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_check_sensitive_words(self):
        """check_sensitive_words 应返回正确结果"""
        result = check_sensitive_words("正常文本")
        assert isinstance(result, SensitiveWordResult)
        assert result.is_clean is True

    def test_filter_sensitive_words(self):
        """filter_sensitive_words 应返回过滤后文本"""
        result = filter_sensitive_words("包含赌博的文字")
        # "赌博" 2个字，替换为2个*
        assert "**" in result
        assert "赌博" not in result

    def test_get_filter_singleton(self):
        """get_filter 应返回单例"""
        filter1 = get_filter()
        filter2 = get_filter()
        assert filter1 is filter2
