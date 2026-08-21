"""PolicyGuard - 策略守卫

基于白名单/黑名单的访问控制策略。
"""
from __future__ import annotations

from enum import Enum
from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class Operation(str, Enum):
    """支持的操作类型"""

    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    DELETE = "delete"
    EXECUTE = "execute"
    LOAD_SKILL = "load_skill"
    LOAD_PROMPT = "load_prompt"
    DELEGATE_TASK = "delegate_task"


class PolicyDecision(NamedTuple):
    """策略决策结果"""

    allowed: bool
    """是否允许"""
    reason: str | None
    """决策理由"""
    requires_approval: bool
    """是否需要人工审批"""


class PolicyGuard:
    """策略守卫

    功能：
    - 白名单操作控制
    - 黑名单操作控制
    - 操作配额限制
    - 操作审计日志
    """

    def __init__(
        self,
        allowed_operations: list[str] | None = None,
        denied_operations: list[str] | None = None,
        requires_approval_operations: list[str] | None = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_write_size: int = 1 * 1024 * 1024,  # 1MB
        allowed_subagents: list[str] | None = None,
        denied_subagents: list[str] | None = None,
    ):
        """初始化策略守卫

        Args:
            allowed_operations: 允许的操作列表
            denied_operations: 禁止的操作列表
            requires_approval_operations: 需要审批的操作列表
            max_file_size: 最大文件大小（字节）
            max_write_size: 最大写入大小（字节）
            allowed_subagents: 允许的 Subagent 列表
            denied_subagents: 禁止的 Subagent 列表
        """
        # 默认允许的操作
        self._allowed_operations = set(allowed_operations or [
            Operation.READ.value,
            Operation.LOAD_SKILL.value,
            Operation.LOAD_PROMPT.value,
        ])

        # 默认禁止的操作
        self._denied_operations = set(denied_operations or [
            Operation.DELETE.value,
            Operation.EXECUTE.value,
        ])

        # 需要审批的操作
        self._approval_operations = set(requires_approval_operations or [
            Operation.WRITE.value,
            Operation.EDIT.value,
        ])

        self._max_file_size = max_file_size
        self._max_write_size = max_write_size

        # Subagent 控制
        self._allowed_subagents = set(allowed_subagents or [])
        self._denied_subagents = set(denied_subagents or [])

        logger.info(
            "policy_guard.init",
            allowed_ops=list(self._allowed_operations),
            denied_ops=list(self._denied_operations),
            approval_ops=list(self._approval_operations),
        )

    def check_operation(self, operation: str, **kwargs) -> PolicyDecision:
        """检查操作是否允许

        Args:
            operation: 操作类型
            **kwargs: 额外参数（如 path, size, subagent 等）

        Returns:
            PolicyDecision: 决策结果
        """
        # 1. 检查是否在禁止列表中
        if operation in self._denied_operations:
            return PolicyDecision(
                allowed=False,
                reason=f"Operation '{operation}' is denied by policy",
                requires_approval=False,
            )

        # 2. 检查是否需要审批
        if operation in self._approval_operations:
            # 检查文件大小
            if "size" in kwargs:
                size = kwargs["size"]
                if size > self._max_write_size:
                    return PolicyDecision(
                        allowed=False,
                        reason=f"File size {size} exceeds max write size {self._max_write_size}",
                        requires_approval=False,
                    )

            return PolicyDecision(
                allowed=True,
                reason=f"Operation '{operation}' requires approval",
                requires_approval=True,
            )

        # 3. 检查是否在允许列表中
        if operation in self._allowed_operations:
            return PolicyDecision(
                allowed=True,
                reason=f"Operation '{operation}' is allowed",
                requires_approval=False,
            )

        # 4. 默认拒绝不在白名单中的操作
        return PolicyDecision(
            allowed=False,
            reason=f"Operation '{operation}' is not in allowed list",
            requires_approval=False,
        )

    def check_subagent(self, subagent_name: str) -> PolicyDecision:
        """检查 Subagent 是否允许使用

        Args:
            subagent_name: Subagent 名称

        Returns:
            PolicyDecision: 决策结果
        """
        # 1. 检查黑名单
        if subagent_name in self._denied_subagents:
            return PolicyDecision(
                allowed=False,
                reason=f"Subagent '{subagent_name}' is denied",
                requires_approval=False,
            )

        # 2. 如果有白名单，检查是否在白名单中
        if self._allowed_subagents:
            if subagent_name not in self._allowed_subagents:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Subagent '{subagent_name}' is not in allowed list",
                    requires_approval=False,
                )

        return PolicyDecision(
            allowed=True,
            reason=f"Subagent '{subagent_name}' is allowed",
            requires_approval=False,
        )

    def check_file_size(self, size: int, operation: str = "read") -> PolicyDecision:
        """检查文件大小是否允许

        Args:
            size: 文件大小（字节）
            operation: 操作类型

        Returns:
            PolicyDecision: 决策结果
        """
        max_size = (
            self._max_write_size
            if operation in [Operation.WRITE.value, Operation.EDIT.value]
            else self._max_file_size
        )

        if size > max_size:
            return PolicyDecision(
                allowed=False,
                reason=f"File size {size} exceeds max size {max_size}",
                requires_approval=False,
            )

        return PolicyDecision(
            allowed=True,
            reason=f"File size {size} is within limit",
            requires_approval=False,
        )

    def is_allowed(self, operation: str, **kwargs) -> bool:
        """快速检查操作是否允许"""
        result = self.check_operation(operation, **kwargs)
        return result.allowed and not result.requires_approval
