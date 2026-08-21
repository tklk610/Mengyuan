"""PathGuard - 路径守卫

防止路径遍历攻击，确保文件操作在允许的目录范围内。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class PathValidationResult(NamedTuple):
    """路径验证结果"""

    is_safe: bool
    """是否安全"""
    normalized_path: str | None
    """规范化后的路径"""
    reason: str | None
    """不安全的理由"""
    is_virtual: bool
    """是否使用虚拟路径"""


class PathGuard:
    """路径守卫

    功能：
    - 防止路径遍历攻击（../）
    - 验证路径是否在允许范围内
    - 规范化路径
    - 支持虚拟模式
    """

    # 系统敏感路径模式
    SENSITIVE_PATTERNS = [
        r"^/etc/",
        r"^/usr/",
        r"^/var/",
        r"^/root/",
        r"^/\.ssh",
        r"^/proc/",
        r"^/sys/",
        r"^C:\\Windows",
        r"^C:\\Program Files",
        r"^C:\\Users\\.*\\\.ssh",
    ]

    def __init__(
        self,
        root_dir: str = ".",
        virtual_mode: bool = True,
        allowed_paths: list[str] | None = None,
        denied_paths: list[str] | None = None,
    ):
        """初始化路径守卫

        Args:
            root_dir: 根目录，文件操作不能超出此目录
            virtual_mode: 虚拟模式，为 True 时不实际访问文件系统
            allowed_paths: 允许访问的路径列表（相对于 root_dir）
            denied_paths: 禁止访问的路径列表（优先于 allowed_paths）
        """
        self._root_dir = Path(root_dir).resolve()
        self._virtual_mode = virtual_mode

        # 默认允许路径
        self._allowed_paths = [
            Path(p).resolve() for p in (allowed_paths or [
                "./skills",
                "./prompts/templates",
                "./workspace",
                "./exports",
            ])
        ]

        # 默认禁止路径
        self._denied_paths = [
            Path(p).resolve() for p in (denied_paths or [
                "./.git",
                "./.venv",
                "./src/ai_agent/config",
            ])
        ]

        # 编译敏感路径正则
        self._sensitive_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATTERNS
        ]

        logger.info(
            "path_guard.init",
            root_dir=str(self._root_dir),
            virtual_mode=virtual_mode,
            allowed_count=len(self._allowed_paths),
            denied_count=len(self._denied_paths),
        )

    def validate(self, path: str) -> PathValidationResult:
        """验证路径是否安全

        Args:
            path: 要验证的路径

        Returns:
            PathValidationResult: 验证结果
        """
        try:
            # 1. 基本检查
            if not path or not path.strip():
                return PathValidationResult(
                    is_safe=False,
                    normalized_path=None,
                    reason="Empty path",
                    is_virtual=self._virtual_mode,
                )

            # 2. 路径遍历检查
            if ".." in path or path.startswith("/"):
                # 检查是否是安全的绝对路径
                abs_path = Path(path).resolve()
                if not self._is_within_root(abs_path):
                    return PathValidationResult(
                        is_safe=False,
                        normalized_path=None,
                        reason="Path traversal detected or absolute path not allowed",
                        is_virtual=self._virtual_mode,
                    )

            # 3. 转换为 Path 对象并解析
            raw_path = Path(path)
            if raw_path.is_absolute():
                resolved_path = raw_path.resolve()
            else:
                resolved_path = (self._root_dir / raw_path).resolve()

            # 4. 检查是否在 root_dir 范围内
            if not self._is_within_root(resolved_path):
                return PathValidationResult(
                    is_safe=False,
                    normalized_path=None,
                    reason=f"Path outside root directory: {self._root_dir}",
                    is_virtual=self._virtual_mode,
                )

            # 5. 检查是否在禁止路径中
            for denied in self._denied_paths:
                try:
                    resolved_path.relative_to(denied)
                    # 在禁止路径中
                    return PathValidationResult(
                        is_safe=False,
                        normalized_path=None,
                        reason=f"Path in denied directory: {denied}",
                        is_virtual=self._virtual_mode,
                    )
                except ValueError:
                    # 不在禁止路径中，继续检查
                    pass

            # 6. 检查系统敏感路径
            path_str = str(resolved_path)
            for pattern in self._sensitive_patterns:
                if pattern.match(path_str):
                    return PathValidationResult(
                        is_safe=False,
                        normalized_path=None,
                        reason=f"System sensitive path detected: {path_str}",
                        is_virtual=self._virtual_mode,
                    )

            # 7. 如果不是虚拟模式，检查文件是否实际存在
            if not self._virtual_mode:
                if not resolved_path.exists():
                    return PathValidationResult(
                        is_safe=False,
                        normalized_path=None,
                        reason=f"Path does not exist (real mode): {resolved_path}",
                        is_virtual=False,
                    )

            # 路径安全
            return PathValidationResult(
                is_safe=True,
                normalized_path=str(resolved_path),
                reason=None,
                is_virtual=self._virtual_mode,
            )

        except Exception as e:
            logger.error("path_guard.validate.error", path=path, error=str(e))
            return PathValidationResult(
                is_safe=False,
                normalized_path=None,
                reason=f"Path validation error: {str(e)}",
                is_virtual=self._virtual_mode,
            )

    def _is_within_root(self, path: Path) -> bool:
        """检查路径是否在 root_dir 范围内"""
        try:
            path.relative_to(self._root_dir)
            return True
        except ValueError:
            return False

    def is_allowed(self, path: str) -> bool:
        """快速检查路径是否允许（只返回 bool）"""
        result = self.validate(path)
        return result.is_safe

    def normalize(self, path: str) -> str | None:
        """规范化路径并返回（如果安全）"""
        result = self.validate(path)
        return result.normalized_path if result.is_safe else None

    @property
    def root_dir(self) -> str:
        """获取根目录"""
        return str(self._root_dir)

    @property
    def virtual_mode(self) -> bool:
        """是否虚拟模式"""
        return self._virtual_mode
