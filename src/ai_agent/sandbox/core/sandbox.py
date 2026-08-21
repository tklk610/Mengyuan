"""FileSandbox - 文件操作沙箱主类

整合 PathGuard、ContentGuard、PolicyGuard、VirtualFS 的统一入口。
"""
from __future__ import annotations

from typing import Any

import structlog

from ai_agent.sandbox.backends.virtual_fs import VirtualFileSystem
from ai_agent.sandbox.core.context import SandboxContext, SandboxContextManager
from ai_agent.sandbox.guards.content_guard import ContentGuard
from ai_agent.sandbox.guards.path_guard import PathGuard
from ai_agent.sandbox.guards.policy_guard import PolicyDecision, PolicyGuard

logger = structlog.get_logger(__name__)


class FileSandbox:
    """文件操作沙箱主类

    功能：
    - 整合 PathGuard + ContentGuard + PolicyGuard
    - 支持虚拟模式和真实模式
    - 统一的操作入口
    - 上下文管理

    用法：
    ```python
    sandbox = FileSandbox(
        root_dir="./workspace",
        virtual_mode=True,
    )

    # 安全读取
    content = await sandbox.read("file.txt")

    # 安全写入（自动内容扫描）
    await sandbox.write("file.txt", content)

    # 使用上下文管理器
    async with SandboxContextManager(sandbox_id="test") as ctx:
        # ctx 是当前沙箱上下文
        ...
    ```
    """

    def __init__(
        self,
        root_dir: str = ".",
        virtual_mode: bool = True,
        # PathGuard 配置
        allowed_paths: list[str] | None = None,
        denied_paths: list[str] | None = None,
        # ContentGuard 配置
        scan_malicious: bool = True,
        scan_injection: bool = True,
        scan_sensitive: bool = True,
        quarantine_suspicious: bool = True,
        # PolicyGuard 配置
        allowed_operations: list[str] | None = None,
        denied_operations: list[str] | None = None,
        requires_approval_operations: list[str] | None = None,
        # Subagent 配置
        allowed_subagents: list[str] | None = None,
    ):
        """初始化文件沙箱

        Args:
            root_dir: 根目录
            virtual_mode: 虚拟模式，为 True 时不实际访问磁盘
            allowed_paths: 允许访问的路径
            denied_paths: 禁止访问的路径
            scan_malicious: 是否扫描恶意代码
            scan_injection: 是否扫描注入攻击
            scan_sensitive: 是否扫描敏感信息
            quarantine_suspicious: 是否隔离可疑内容
            allowed_operations: 允许的操作
            denied_operations: 禁止的操作
            requires_approval_operations: 需要审批的操作
            allowed_subagents: 允许的 Subagent
        """
        # 初始化各个守卫
        self._path_guard = PathGuard(
            root_dir=root_dir,
            virtual_mode=virtual_mode,
            allowed_paths=allowed_paths,
            denied_paths=denied_paths,
        )

        self._content_guard = ContentGuard(
            scan_malicious=scan_malicious,
            scan_injection=scan_injection,
            scan_sensitive=scan_sensitive,
            quarantine_suspicious=quarantine_suspicious,
        )

        self._policy_guard = PolicyGuard(
            allowed_operations=allowed_operations,
            denied_operations=denied_operations,
            requires_approval_operations=requires_approval_operations,
            allowed_subagents=allowed_subagents,
        )

        # 虚拟文件系统
        self._vfs = VirtualFileSystem() if virtual_mode else None

        # 配置
        self._root_dir = root_dir
        self._virtual_mode = virtual_mode

        logger.info(
            "file_sandbox.init",
            root_dir=root_dir,
            virtual_mode=virtual_mode,
            path_guard_enabled=True,
            content_guard_enabled=True,
            policy_guard_enabled=True,
        )

    # === 路径操作 ===

    def is_path_safe(self, path: str) -> bool:
        """检查路径是否安全"""
        return self._path_guard.is_allowed(path)

    def normalize_path(self, path: str) -> str | None:
        """规范化并验证路径"""
        return self._path_guard.normalize(path)

    # === 内容操作 ===

    def scan_content(self, content: str) -> Any:
        """扫描内容是否安全

        Returns:
            ContentScanResult: 扫描结果
        """
        return self._content_guard.scan(content)

    def is_content_safe(self, content: str) -> bool:
        """快速检查内容是否安全"""
        return self._content_guard.is_safe(content)

    # === 策略操作 ===

    def check_policy(self, operation: str, **kwargs) -> PolicyDecision:
        """检查操作策略

        Returns:
            PolicyDecision: 策略决策
        """
        return self._policy_guard.check_operation(operation, **kwargs)

    def check_subagent(self, subagent_name: str) -> PolicyDecision:
        """检查 Subagent 策略"""
        return self._policy_guard.check_subagent(subagent_name)

    # === 文件操作 ===

    async def read(self, path: str) -> str | None:
        """安全读取文件

        Args:
            path: 文件路径

        Returns:
            str | None: 文件内容，失败返回 None
        """
        # 1. 路径验证
        if not self.is_path_safe(path):
            logger.warning("sandbox.read.path_denied", path=path)
            return None

        # 2. 策略检查
        decision = self.check_policy("read")
        if not decision.allowed:
            logger.warning("sandbox.read.policy_denied", path=path, reason=decision.reason)
            return None

        # 3. 虚拟模式读取
        if self._virtual_mode and self._vfs:
            content = self._vfs.read(path)
            logger.debug("sandbox.read.vfs", path=path)
            return content

        # 4. 真实模式读取（仅在 virtual_mode=False 时）
        if not self._virtual_mode:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.debug("sandbox.read.real", path=path)
                return content
            except Exception as e:
                logger.error("sandbox.read.error", path=path, error=str(e))
                return None

        return None

    async def write(self, path: str, content: str, require_approval: bool = True) -> bool:
        """安全写入文件

        Args:
            path: 文件路径
            content: 文件内容
            require_approval: 是否需要审批（对于危险操作）

        Returns:
            bool: 是否成功
        """
        # 1. 路径验证
        if not self.is_path_safe(path):
            logger.warning("sandbox.write.path_denied", path=path)
            return False

        # 2. 内容扫描
        scan_result = self.scan_content(content)
        if not scan_result.is_safe:
            logger.warning(
                "sandbox.write.content_unsafe",
                path=path,
                risk_level=scan_result.risk_level,
                issues=scan_result.issues,
            )
            # 可疑内容隔离
            if scan_result.sanitized_content:
                content = scan_result.sanitized_content
            else:
                return False

        # 3. 策略检查
        decision = self.check_policy("write", size=len(content))
        if not decision.allowed:
            logger.warning("sandbox.write.policy_denied", path=path, reason=decision.reason)
            return False

        # 4. 需要审批时记录但不阻止
        if decision.requires_approval and require_approval:
            logger.info("sandbox.write.requires_approval", path=path)
            # 创建待审批记录
            ctx = self._context_manager._ctx if hasattr(self, "_context_manager") else None
            if ctx:
                ctx.add_pending_approval("write", path, {"content": content[:100]})

        # 5. 虚拟模式写入
        if self._virtual_mode and self._vfs:
            success = self._vfs.write(path, content)
            logger.debug("sandbox.write.vfs", path=path, success=success)
            return success

        # 6. 真实模式写入
        if not self._virtual_mode:
            try:
                import os
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.debug("sandbox.write.real", path=path)
                return True
            except Exception as e:
                logger.error("sandbox.write.error", path=path, error=str(e))
                return False

        return False

    async def delete(self, path: str) -> bool:
        """安全删除文件（默认禁止）"""
        # 1. 路径验证
        if not self.is_path_safe(path):
            logger.warning("sandbox.delete.path_denied", path=path)
            return False

        # 2. 策略检查（delete 默认禁止）
        decision = self.check_policy("delete")
        if not decision.allowed:
            logger.warning("sandbox.delete.policy_denied", path=path, reason=decision.reason)
            return False

        # 3. 虚拟模式删除
        if self._virtual_mode and self._vfs:
            return self._vfs.delete(path)

        logger.warning("sandbox.delete.real_mode_denied", path=path)
        return False

    # === 工具方法 ===

    def list_files(self, pattern: str = "*") -> list[str]:
        """列出文件"""
        if self._virtual_mode and self._vfs:
            return self._vfs.list(pattern)
        return []

    def get_context(self) -> SandboxContext:
        """获取沙箱上下文"""
        return getattr(self, "_context_manager", None)

    # === 属性 ===

    @property
    def root_dir(self) -> str:
        """获取根目录"""
        return self._root_dir

    @property
    def virtual_mode(self) -> bool:
        """是否虚拟模式"""
        return self._virtual_mode

    @property
    def vfs(self) -> VirtualFileSystem | None:
        """获取虚拟文件系统（仅虚拟模式）"""
        return self._vfs
