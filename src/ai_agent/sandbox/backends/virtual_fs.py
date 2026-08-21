"""VirtualFileSystem - 虚拟文件系统

在内存中模拟文件系统操作，不实际写入磁盘。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class VirtualFileEntry(NamedTuple):
    """虚拟文件条目"""

    path: str
    content: str
    created_at: datetime
    modified_at: datetime
    size: int
    is_directory: bool = False


class VirtualFileSystem:
    """虚拟文件系统

    特性：
    - 所有操作在内存中进行，不实际访问磁盘
    - 支持基本的文件操作（read/write/list）
    - 操作审计日志
    - 可导出/导入状态
    """

    def __init__(self):
        """初始化虚拟文件系统"""
        self._store: dict[str, VirtualFileEntry] = {}
        self._operation_log: list[dict] = []

    # === 文件操作 ===

    def write(self, path: str, content: str) -> bool:
        """虚拟写入文件

        Args:
            path: 文件路径
            content: 文件内容

        Returns:
            bool: 是否成功
        """
        now = datetime.now()
        entry = VirtualFileEntry(
            path=path,
            content=content,
            created_at=now,
            modified_at=now,
            size=len(content.encode("utf-8")),
            is_directory=False,
        )
        self._store[path] = entry
        self._log_operation("write", path, {"size": len(content)})
        logger.debug("vfs.write", path=path, size=len(content))
        return True

    def read(self, path: str) -> str | None:
        """虚拟读取文件

        Args:
            path: 文件路径

        Returns:
            str | None: 文件内容，不存在则返回 None
        """
        entry = self._store.get(path)
        if entry:
            self._log_operation("read", path, {"size": entry.size})
            logger.debug("vfs.read", path=path, size=entry.size)
            return entry.content
        return None

    def exists(self, path: str) -> bool:
        """检查文件是否存在

        Args:
            path: 文件路径

        Returns:
            bool: 是否存在
        """
        return path in self._store

    def delete(self, path: str) -> bool:
        """虚拟删除文件

        Args:
            path: 文件路径

        Returns:
            bool: 是否成功
        """
        if path in self._store:
            del self._store[path]
            self._log_operation("delete", path)
            logger.debug("vfs.delete", path=path)
            return True
        return False

    def list(self, pattern: str = "*") -> list[str]:
        """列出匹配的文件

        Args:
            pattern: 文件模式（支持 * 和 ?）

        Returns:
            list[str]: 匹配的文件路径列表
        """
        import fnmatch

        paths = list(self._store.keys())
        matched = [p for p in paths if fnmatch.fnmatch(p, pattern)]
        self._log_operation("list", pattern, {"matched_count": len(matched)})
        return matched

    # === 目录操作 ===

    def mkdir(self, path: str) -> bool:
        """创建虚拟目录

        Args:
            path: 目录路径

        Returns:
            bool: 是否成功
        """
        now = datetime.now()
        entry = VirtualFileEntry(
            path=path,
            content="",
            created_at=now,
            modified_at=now,
            size=0,
            is_directory=True,
        )
        self._store[path] = entry
        self._log_operation("mkdir", path)
        logger.debug("vfs.mkdir", path=path)
        return True

    def is_directory(self, path: str) -> bool:
        """检查是否是目录

        Args:
            path: 路径

        Returns:
            bool: 是否是目录
        """
        entry = self._store.get(path)
        return entry.is_directory if entry else False

    # === 审计日志 ===

    def _log_operation(self, operation: str, path: str, details: dict = None):
        """记录操作日志"""
        self._operation_log.append({
            "operation": operation,
            "path": path,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        })

    @property
    def operation_log(self) -> list[dict]:
        """获取操作日志"""
        return self._operation_log.copy()

    def clear_log(self):
        """清空操作日志"""
        self._operation_log.clear()

    # === 状态管理 ===

    def export_state(self) -> str:
        """导出虚拟文件系统状态为 JSON

        Returns:
            str: JSON 格式的状态
        """
        state = {
            "files": {
                path: {
                    "content": entry.content,
                    "created_at": entry.created_at.isoformat(),
                    "modified_at": entry.modified_at.isoformat(),
                    "size": entry.size,
                    "is_directory": entry.is_directory,
                }
                for path, entry in self._store.items()
            },
            "operation_count": len(self._operation_log),
        }
        return json.dumps(state, ensure_ascii=False, indent=2)

    def import_state(self, state_json: str) -> bool:
        """从 JSON 导入虚拟文件系统状态

        Args:
            state_json: JSON 格式的状态

        Returns:
            bool: 是否成功
        """
        try:
            state = json.loads(state_json)
            self._store.clear()
            for path, info in state["files"].items():
                self._store[path] = VirtualFileEntry(
                    path=path,
                    content=info["content"],
                    created_at=datetime.fromisoformat(info["created_at"]),
                    modified_at=datetime.fromisoformat(info["modified_at"]),
                    size=info["size"],
                    is_directory=info.get("is_directory", False),
                )
            logger.info("vfs.import_state", file_count=len(self._store))
            return True
        except Exception as e:
            logger.error("vfs.import_state.error", error=str(e))
            return False

    def clear(self):
        """清空虚拟文件系统"""
        self._store.clear()
        self._operation_log.clear()
        logger.info("vfs.clear")

    @property
    def file_count(self) -> int:
        """文件数量"""
        return len(self._store)

    @property
    def total_size(self) -> int:
        """总大小（字节）"""
        return sum(entry.size for entry in self._store.values())
