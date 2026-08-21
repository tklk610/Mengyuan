"""Unit Tests for VirtualFileSystem

测试虚拟文件系统功能：
- 读写操作
- 目录操作
- 状态导出/导入
"""
import pytest

from ai_agent.sandbox.backends.virtual_fs import VirtualFileSystem


class TestVirtualFileSystem:
    """VirtualFileSystem 单元测试"""

    def test_write_and_read(self):
        """写入后读取"""
        vfs = VirtualFileSystem()
        vfs.write("/test/file.txt", "Hello World")
        content = vfs.read("/test/file.txt")
        assert content == "Hello World"

    def test_read_nonexistent(self):
        """读取不存在的文件"""
        vfs = VirtualFileSystem()
        content = vfs.read("/nonexistent.txt")
        assert content is None

    def test_exists(self):
        """文件存在检查"""
        vfs = VirtualFileSystem()
        assert vfs.exists("/test.txt") is False
        vfs.write("/test.txt", "content")
        assert vfs.exists("/test.txt") is True

    def test_delete(self):
        """删除文件"""
        vfs = VirtualFileSystem()
        vfs.write("/test.txt", "content")
        assert vfs.exists("/test.txt") is True
        vfs.delete("/test.txt")
        assert vfs.exists("/test.txt") is False

    def test_delete_nonexistent(self):
        """删除不存在的文件"""
        vfs = VirtualFileSystem()
        result = vfs.delete("/nonexistent.txt")
        assert result is False

    def test_list(self):
        """列出文件"""
        vfs = VirtualFileSystem()
        vfs.write("/test1.txt", "content1")
        vfs.write("/test2.txt", "content2")
        vfs.write("/other/doc.txt", "content3")

        files = vfs.list("*.txt")
        assert len(files) == 3

        # 注意：fnmatch 的 * 不匹配 /
        txt_files = vfs.list("/test*.txt")
        assert len(txt_files) >= 2

    def test_mkdir(self):
        """创建目录"""
        vfs = VirtualFileSystem()
        vfs.mkdir("/newdir")
        assert vfs.is_directory("/newdir") is True

    def test_operation_log(self):
        """操作日志"""
        vfs = VirtualFileSystem()
        vfs.write("/test.txt", "content")
        vfs.read("/test.txt")

        log = vfs.operation_log
        assert len(log) == 2
        assert log[0]["operation"] == "write"
        assert log[1]["operation"] == "read"

    def test_clear_log(self):
        """清空日志"""
        vfs = VirtualFileSystem()
        vfs.write("/test.txt", "content")
        assert len(vfs.operation_log) == 1
        vfs.clear_log()
        assert len(vfs.operation_log) == 0

    def test_export_state(self):
        """导出状态"""
        vfs = VirtualFileSystem()
        vfs.write("/test.txt", "Hello")

        state_json = vfs.export_state()
        assert "files" in state_json
        assert "/test.txt" in state_json

    def test_import_state(self):
        """导入状态"""
        vfs = VirtualFileSystem()
        original_state = '{"files": {"/imported.txt": {"content": "Imported", "created_at": "2024-01-01T00:00:00", "modified_at": "2024-01-01T00:00:00", "size": 8, "is_directory": false}}}'

        result = vfs.import_state(original_state)
        assert result is True
        assert vfs.exists("/imported.txt") is True
        assert vfs.read("/imported.txt") == "Imported"

    def test_clear(self):
        """清空文件系统"""
        vfs = VirtualFileSystem()
        vfs.write("/test1.txt", "content1")
        vfs.write("/test2.txt", "content2")
        assert vfs.file_count == 2

        vfs.clear()
        assert vfs.file_count == 0

    def test_total_size(self):
        """总大小"""
        vfs = VirtualFileSystem()
        vfs.write("/small.txt", "hi")  # 2 bytes
        vfs.write("/large.txt", "hello world")  # 11 bytes

        assert vfs.total_size == 13
