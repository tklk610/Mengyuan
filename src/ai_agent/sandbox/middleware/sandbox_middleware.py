"""SandboxMiddleware - 沙箱中间件

拦截危险操作，触发 HITL 人工审批。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import structlog

from ai_agent.sandbox.core.context import SandboxContext

logger = structlog.get_logger(__name__)


class OperationType(str, Enum):
    """操作类型"""

    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    DELETE = "delete"
    EXECUTE = "execute"
    LOAD_SKILL = "load_skill"
    DELEGATE_TASK = "delegate_task"


@dataclass
class OperationRequest:
    """操作请求"""

    operation: OperationType
    """操作类型"""
    path: str | None
    """文件路径（如果有）"""
    params: dict
    """操作参数"""
    subagent_name: str | None
    """Subagent 名称（如果是任务委派）"""


@dataclass
class OperationResponse:
    """操作响应"""

    allowed: bool
    """是否允许执行"""
    executed: bool
    """是否已执行"""
    result: Any
    """执行结果"""
    error: str | None
    """错误信息"""
    requires_approval: bool
    """是否需要人工审批"""
    approval_id: str | None
    """审批 ID（如果需要审批）"""


class SandboxMiddleware:
    """沙箱中间件

    功能：
    - 拦截所有文件操作
    - 危险操作触发 HITL 审批
    - 操作审计日志
    - 配额控制

    用法：
    ```python
    middleware = SandboxMiddleware(sandbox=file_sandbox)

    # 拦截文件写入
    response = await middleware.handle_write(
        path="/path/to/file",
        content="...",
        params={}
    )

    if response.requires_approval:
        # 创建待审批项
        approval_id = response.approval_id
        # ...
    ```
    """

    def __init__(
        self,
        sandbox: Any,  # FileSandbox
        hitl_enabled: bool = True,
        auto_approve_safe: bool = False,
    ):
        """初始化沙箱中间件

        Args:
            sandbox: FileSandbox 实例
            hitl_enabled: 是否启用 HITL 审批
            auto_approve_safe: 是否自动批准安全操作
        """
        self._sandbox = sandbox
        self._hitl_enabled = hitl_enabled
        self._auto_approve_safe = auto_approve_safe
        self._pending_approvals: dict[str, OperationRequest] = {}

        logger.info(
            "sandbox_middleware.init",
            hitl_enabled=hitl_enabled,
            auto_approve_safe=auto_approve_safe,
        )

    # === 操作处理 ===

    async def handle_read(self, path: str, **params) -> OperationResponse:
        """处理文件读取

        Args:
            path: 文件路径
            **params: 额外参数

        Returns:
            OperationResponse: 操作响应
        """
        # 1. 路径安全检查
        if not self._sandbox.is_path_safe(path):
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error=f"Path not allowed: {path}",
                requires_approval=False,
                approval_id=None,
            )

        # 2. 策略检查
        decision = self._sandbox.check_policy("read")
        if not decision.allowed:
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error=decision.reason,
                requires_approval=False,
                approval_id=None,
            )

        # 3. 执行读取
        import asyncio
        content = await self._sandbox.read(path)

        if content is None:
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error="Failed to read file",
                requires_approval=False,
                approval_id=None,
            )

        return OperationResponse(
            allowed=True,
            executed=True,
            result=content,
            error=None,
            requires_approval=False,
            approval_id=None,
        )

    async def handle_write(
        self, path: str, content: str, **params
    ) -> OperationResponse:
        """处理文件写入

        Args:
            path: 文件路径
            content: 文件内容
            **params: 额外参数

        Returns:
            OperationResponse: 操作响应
        """
        # 1. 路径安全检查
        if not self._sandbox.is_path_safe(path):
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error=f"Path not allowed: {path}",
                requires_approval=False,
                approval_id=None,
            )

        # 2. 内容安全检查
        scan_result = self._sandbox.scan_content(content)
        if not scan_result.is_safe:
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error=f"Content unsafe: {', '.join(scan_result.issues)}",
                requires_approval=False,
                approval_id=None,
            )

        # 3. 策略检查
        decision = self._sandbox.check_policy("write", size=len(content))
        if not decision.allowed:
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error=decision.reason,
                requires_approval=False,
                approval_id=None,
            )

        # 4. 检查是否需要审批
        if decision.requires_approval and self._hitl_enabled:
            import uuid
            approval_id = str(uuid.uuid4())[:8]

            request = OperationRequest(
                operation=OperationType.WRITE,
                path=path,
                params={"content": content, **params},
                subagent_name=None,
            )
            self._pending_approvals[approval_id] = request

            return OperationResponse(
                allowed=True,
                executed=False,
                result=None,
                error=None,
                requires_approval=True,
                approval_id=approval_id,
            )

        # 5. 执行写入
        import asyncio
        success = await self._sandbox.write(path, content, require_approval=False)

        return OperationResponse(
            allowed=success,
            executed=success,
            result=success,
            error=None if success else "Write failed",
            requires_approval=False,
            approval_id=None,
        )

    async def handle_delete(self, path: str, **params) -> OperationResponse:
        """处理文件删除（默认禁止）"""
        return OperationResponse(
            allowed=False,
            executed=False,
            result=None,
            error="Delete operation is not allowed by sandbox policy",
            requires_approval=False,
            approval_id=None,
        )

    async def handle_delegate_task(
        self, subagent_name: str, instruction: str, **params
    ) -> OperationResponse:
        """处理任务委派

        Args:
            subagent_name: Subagent 名称
            instruction: 任务指令
            **params: 额外参数

        Returns:
            OperationResponse: 操作响应
        """
        # 1. Subagent 策略检查
        decision = self._sandbox.check_subagent(subagent_name)
        if not decision.allowed:
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error=decision.reason,
                requires_approval=False,
                approval_id=None,
            )

        # 2. 指令内容检查
        scan_result = self._sandbox.scan_content(instruction)
        if not scan_result.is_safe:
            return OperationResponse(
                allowed=False,
                executed=False,
                result=None,
                error=f"Instruction unsafe: {', '.join(scan_result.issues)}",
                requires_approval=False,
                approval_id=None,
            )

        # 3. 需要审批
        if self._hitl_enabled:
            import uuid
            approval_id = str(uuid.uuid4())[:8]

            request = OperationRequest(
                operation=OperationType.DELEGATE_TASK,
                path=None,
                params={"instruction": instruction, **params},
                subagent_name=subagent_name,
            )
            self._pending_approvals[approval_id] = request

            return OperationResponse(
                allowed=True,
                executed=False,
                result=None,
                error=None,
                requires_approval=True,
                approval_id=approval_id,
            )

        # 4. 自动批准（如果启用）
        return OperationResponse(
            allowed=True,
            executed=False,
            result=None,
            error=None,
            requires_approval=False,
            approval_id=None,
        )

    # === 审批管理 ===

    def get_pending_approvals(self) -> list[dict]:
        """获取待审批列表"""
        return [
            {
                "approval_id": aid,
                "operation": req.operation.value,
                "path": req.path,
                "subagent": req.subagent_name,
                "params": req.params,
            }
            for aid, req in self._pending_approvals.items()
        ]

    def approve(self, approval_id: str) -> bool:
        """批准操作

        Args:
            approval_id: 审批 ID

        Returns:
            bool: 是否成功
        """
        if approval_id not in self._pending_approvals:
            return False

        del self._pending_approvals[approval_id]
        logger.info("sandbox_middleware.approve", approval_id=approval_id)
        return True

    def reject(self, approval_id: str, reason: str = None) -> bool:
        """拒绝操作

        Args:
            approval_id: 审批 ID
            reason: 拒绝理由

        Returns:
            bool: 是否成功
        """
        if approval_id not in self._pending_approvals:
            return False

        req = self._pending_approvals[approval_id]
        del self._pending_approvals[approval_id]
        logger.info(
            "sandbox_middleware.reject",
            approval_id=approval_id,
            operation=req.operation.value,
            reason=reason,
        )
        return True

    @property
    def pending_count(self) -> int:
        """待审批数量"""
        return len(self._pending_approvals)
