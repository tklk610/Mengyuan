"""SandboxContext - 沙箱上下文

维护沙箱运行时的上下文状态。
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# 上下文变量
_current_sandbox: ContextVar["SandboxContext | None"] = ContextVar(
    "current_sandbox", default=None
)


@dataclass
class SandboxContext:
    """沙箱上下文

    维护沙箱运行时的状态：
    - 当前沙箱配置
    - 操作历史
    - 审批状态
    - 配额使用
    """

    sandbox_id: str
    """沙箱唯一标识"""
    root_dir: str
    """根目录"""
    virtual_mode: bool = True
    """是否虚拟模式"""
    created_at: datetime = field(default_factory=datetime.now)
    """创建时间"""

    # 操作统计
    read_count: int = 0
    write_count: int = 0
    delete_count: int = 0
    total_bytes_read: int = 0
    total_bytes_written: int = 0

    # 审批状态
    pending_approvals: list[dict] = field(default_factory=list)
    """待审批的操作"""
    approved_operations: list[dict] = field(default_factory=list)
    """已批准的操作"""
    rejected_operations: list[dict] = field(default_factory=list)
    """已拒绝的操作"""

    # 隔离区
    quarantined_items: list[dict] = field(default_factory=list)
    """隔离的可疑内容"""

    def record_read(self, path: str, size: int = 0):
        """记录读取操作"""
        self.read_count += 1
        self.total_bytes_read += size

    def record_write(self, path: str, size: int = 0):
        """记录写入操作"""
        self.write_count += 1
        self.total_bytes_written += size

    def record_delete(self, path: str):
        """记录删除操作"""
        self.delete_count += 1

    def add_pending_approval(self, operation: str, path: str, params: dict):
        """添加待审批操作"""
        self.pending_approvals.append({
            "operation": operation,
            "path": path,
            "params": params,
            "added_at": datetime.now().isoformat(),
        })

    def approve(self, operation_id: int) -> bool:
        """批准操作"""
        if 0 <= operation_id < len(self.pending_approvals):
            op = self.pending_approvals.pop(operation_id)
            op["approved_at"] = datetime.now().isoformat()
            self.approved_operations.append(op)
            logger.info("sandbox.approve", operation=op)
            return True
        return False

    def reject(self, operation_id: int, reason: str = None):
        """拒绝操作"""
        if 0 <= operation_id < len(self.pending_approvals):
            op = self.pending_approvals.pop(operation_id)
            op["rejected_at"] = datetime.now().isoformat()
            op["reject_reason"] = reason
            self.rejected_operations.append(op)
            logger.info("sandbox.reject", operation=op, reason=reason)
            return True
        return False

    def quarantine(self, path: str, content: str, reason: str):
        """隔离可疑内容"""
        self.quarantined_items.append({
            "path": path,
            "content_hash": hash(content),
            "reason": reason,
            "quarantined_at": datetime.now().isoformat(),
        })
        logger.warning("sandbox.quarantine", path=path, reason=reason)

    @property
    def stats(self) -> dict:
        """获取沙箱统计"""
        return {
            "sandbox_id": self.sandbox_id,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "delete_count": self.delete_count,
            "total_bytes_read": self.total_bytes_read,
            "total_bytes_written": self.total_bytes_written,
            "pending_approvals": len(self.pending_approvals),
            "approved_operations": len(self.approved_operations),
            "rejected_operations": len(self.rejected_operations),
            "quarantined_items": len(self.quarantined_items),
        }


# === Context Manager ===

def get_current_sandbox() -> SandboxContext | None:
    """获取当前沙箱上下文"""
    return _current_sandbox.get()


def set_current_sandbox(ctx: SandboxContext | None):
    """设置当前沙箱上下文"""
    _current_sandbox.set(ctx)


class SandboxContextManager:
    """沙箱上下文管理器

    用法：
    async with SandboxContextManager(sandbox_id="test") as ctx:
        # ctx 是当前沙箱上下文
        ctx.record_write("/path/to/file", 100)
    """

    def __init__(self, sandbox_id: str, root_dir: str = ".", virtual_mode: bool = True):
        self._ctx = SandboxContext(
            sandbox_id=sandbox_id,
            root_dir=root_dir,
            virtual_mode=virtual_mode,
        )

    async def __aenter__(self) -> SandboxContext:
        set_current_sandbox(self._ctx)
        logger.info("sandbox.context.enter", sandbox_id=self._ctx.sandbox_id)
        return self._ctx

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.info(
            "sandbox.context.exit",
            sandbox_id=self._ctx.sandbox_id,
            stats=self._ctx.stats,
        )
        set_current_sandbox(None)
        return False  # 不吞没异常
