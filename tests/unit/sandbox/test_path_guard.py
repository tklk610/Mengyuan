"""Unit Tests for PathGuard

测试路径守卫功能：
- 路径遍历防护
- 允许/禁止路径检查
- 系统敏感路径保护
"""
import pytest

from ai_agent.sandbox.guards.path_guard import PathGuard, PathValidationResult


class TestPathGuard:
    """PathGuard 单元测试"""

    def test_empty_path(self):
        """空路径应被拒绝"""
        guard = PathGuard(root_dir=".", virtual_mode=True)
        result = guard.validate("")
        assert result.is_safe is False
        assert "Empty path" in (result.reason or "")

    def test_path_traversal_forward(self):
        """../ 路径遍历应被拒绝"""
        guard = PathGuard(root_dir="/project", virtual_mode=True)
        result = guard.validate("../etc/passwd")
        assert result.is_safe is False

    def test_path_traversal_backward(self):
        """..\\ 路径遍历应被拒绝"""
        guard = PathGuard(root_dir="C:\\project", virtual_mode=True)
        result = guard.validate("..\\Windows\\System32")
        assert result.is_safe is False

    def test_within_root(self):
        """root_dir 内的路径应通过"""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            guard = PathGuard(root_dir=tmpdir, virtual_mode=True)
            test_file = os.path.join(tmpdir, "test.txt")
            result = guard.validate(test_file)
            # 路径在 root_dir 内
            assert result.is_safe is True

    def test_system_sensitive_path(self):
        """系统敏感路径应被拒绝"""
        guard = PathGuard(root_dir=".", virtual_mode=True)

        # Windows 敏感路径
        result = guard.validate("C:\\Windows\\System32\\config\\SAM")
        assert result.is_safe is False

    def test_normalize(self):
        """路径规范化"""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            guard = PathGuard(root_dir=tmpdir, virtual_mode=True)
            normalized = guard.normalize(os.path.join(tmpdir, "sub", "test.txt"))
            assert normalized is not None
            assert "sub" in normalized

    def test_quick_is_allowed(self):
        """快速检查方法"""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            guard = PathGuard(root_dir=tmpdir, virtual_mode=True)
            assert guard.is_allowed(os.path.join(tmpdir, "test.txt")) is True
            assert guard.is_allowed("../etc/passwd") is False

    def test_virtual_mode_flag(self):
        """虚拟模式标志"""
        guard_virtual = PathGuard(root_dir=".", virtual_mode=True)
        guard_real = PathGuard(root_dir=".", virtual_mode=False)

        assert guard_virtual.virtual_mode is True
        assert guard_real.virtual_mode is False

    def test_denied_path(self):
        """禁止路径应被拒绝"""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            denied_dir = os.path.join(tmpdir, "denied")

            guard = PathGuard(
                root_dir=tmpdir,
                virtual_mode=True,
                denied_paths=[denied_dir],
            )

            # denied 路径应被拒绝
            denied_file = os.path.join(denied_dir, "test.txt")
            result = guard.validate(denied_file)
            assert result.is_safe is False

    def test_absolute_path_within_root(self):
        """绝对路径在 root_dir 内应通过"""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            guard = PathGuard(root_dir=tmpdir, virtual_mode=True)
            test_path = os.path.join(tmpdir, "subdir", "file.txt")
            result = guard.validate(test_path)
            assert result.is_safe is True
