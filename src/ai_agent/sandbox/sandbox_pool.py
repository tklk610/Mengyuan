"""SandboxPool - 沙箱池 + 用户隔离

提供：
- 用户级沙箱隔离
- 沙箱池管理
- 预热机制
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog

from ai_agent.sandbox.core.sandbox import FileSandbox

logger = structlog.get_logger(__name__)


@dataclass
class UserSandbox:
    """用户沙箱实例"""

    user_id: str
    """用户 ID"""
    sandbox: FileSandbox
    """沙箱实例"""
    created_at: float
    """创建时间"""
    last_used_at: float
    """最后使用时间"""
    use_count: int = 0
    """使用次数"""
    is_warmed: bool = False
    """是否已预热"""

    @property
    def idle_seconds(self) -> float:
        """空闲秒数"""
        return time.time() - self.last_used_at

    def touch(self):
        """更新最后使用时间"""
        self.last_used_at = time.time()
        self.use_count += 1


class SandboxPool:
    """沙箱池

    功能：
    - 用户级沙箱隔离
    - 沙箱池管理
    - 预热机制
    - 空闲回收

    用法：
    ```python
    pool = SandboxPool(max_size=10, idle_timeout=300)

    # 获取用户沙箱
    async with pool.get_sandbox("user_123") as sandbox:
        await sandbox.read("file.txt")

    # 或上下文管理器
    sandbox = await pool.acquire("user_123")
    try:
        await sandbox.read("file.txt")
    finally:
        pool.release("user_123")
    ```
    """

    def __init__(
        self,
        max_size: int = 10,
        idle_timeout: float = 300.0,
        warmup_timeout: float = 30.0,
    ):
        """初始化沙箱池

        Args:
            max_size: 最大沙箱实例数
            idle_timeout: 空闲超时（秒），超时后回收
            warmup_timeout: 预热超时（秒）
        """
        self._max_size = max_size
        self._idle_timeout = idle_timeout
        self._warmup_timeout = warmup_timeout

        # 用户沙箱映射
        self._sandboxes: dict[str, UserSandbox] = {}

        # 锁
        self._lock = asyncio.Lock()

        # 预热状态
        self._warmup_task: asyncio.Task | None = None
        self._is_warming = False

        logger.info(
            "sandbox_pool.init",
            max_size=max_size,
            idle_timeout=idle_timeout,
        )

    # === 用户隔离 ===

    @asynccontextmanager
    async def get_sandbox(self, user_id: str) -> FileSandbox:
        """获取用户沙箱（异步上下文管理器）

        Args:
            user_id: 用户 ID

        Yields:
            FileSandbox: 用户沙箱实例
        """
        sandbox = await self.acquire(user_id)
        try:
            yield sandbox
        finally:
            self.release(user_id)

    async def acquire(self, user_id: str) -> FileSandbox:
        """获取用户沙箱

        Args:
            user_id: 用户 ID

        Returns:
            FileSandbox: 用户沙箱实例
        """
        async with self._lock:
            # 检查是否已存在
            if user_id in self._sandboxes:
                user_sb = self._sandboxes[user_id]
                user_sb.touch()
                logger.debug("sandbox_pool.reuse", user_id=user_id, use_count=user_sb.use_count)
                return user_sb.sandbox

            # 检查容量
            if len(self._sandboxes) >= self._max_size:
                # 回收最久未使用的沙箱
                await self._evict_lru()

            # 创建新沙箱
            sandbox = await self._create_sandbox(user_id)
            user_sb = UserSandbox(
                user_id=user_id,
                sandbox=sandbox,
                created_at=time.time(),
                last_used_at=time.time(),
            )
            self._sandboxes[user_id] = user_sb

            logger.info("sandbox_pool.acquire", user_id=user_id, pool_size=len(self._sandboxes))
            return sandbox

    def release(self, user_id: str):
        """释放沙箱（更新最后使用时间）

        Args:
            user_id: 用户 ID
        """
        if user_id in self._sandboxes:
            self._sandboxes[user_id].touch()
            logger.debug("sandbox_pool.release", user_id=user_id)

    async def _evict_lru(self):
        """驱逐最久未使用的沙箱"""
        if not self._sandboxes:
            return

        # 找最久未使用的
        lru_user_id = min(
            self._sandboxes,
            key=lambda uid: self._sandboxes[uid].last_used_at
        )
        del self._sandboxes[lru_user_id]
        logger.info("sandbox_pool.evict", user_id=lru_user_id, pool_size=len(self._sandboxes))

    # === 沙箱创建 ===

    async def _create_sandbox(self, user_id: str) -> FileSandbox:
        """创建用户沙箱

        Args:
            user_id: 用户 ID

        Returns:
            FileSandbox: 新沙箱实例
        """
        sandbox = FileSandbox(
            root_dir=f"./workspace/{user_id}",  # 用户隔离目录
            virtual_mode=True,
        )
        return sandbox

    # === 预热机制 ===

    async def warmup(self, user_id: str | None = None):
        """预热沙箱

        Args:
            user_id: 指定用户，不指定则预热所有
        """
        if user_id:
            # 预热指定用户
            await self._warmup_user(user_id)
        else:
            # 预热所有用户
            await self._warmup_all()

    async def _warmup_user(self, user_id: str):
        """预热指定用户沙箱"""
        if user_id in self._sandboxes:
            user_sb = self._sandboxes[user_id]
            if not user_sb.is_warmed:
                await self._do_warmup(user_sb)
                user_sb.is_warmed = True
                logger.info("sandbox_pool.warmed_single", user_id=user_id)

    async def _warmup_all(self):
        """预热所有沙箱"""
        if self._is_warming:
            logger.warning("sandbox_pool.warming_in_progress")
            return

        self._is_warming = True
        try:
            warmups = [
                self._warmup_user(uid)
                for uid in self._sandboxes
            ]
            if warmups:
                await asyncio.gather(*warmups)
            logger.info("sandbox_pool.warmed_all", count=len(self._sandboxes))
        finally:
            self._is_warming = False

    async def _do_warmup(self, user_sb: UserSandbox):
        """执行预热逻辑"""
        # 预热：加载常用模块、初始化资源
        # 这里可以预加载 LLM 模型、初始化连接等
        await asyncio.sleep(0.1)  # 模拟预热延迟

    def is_warmed(self, user_id: str) -> bool:
        """检查沙箱是否已预热"""
        return self._sandboxes.get(user_id, None) and self._sandboxes[user_id].is_warmed

    # === 资源管理 ===

    async def cleanup_user(self, user_id: str):
        """清理用户沙箱

        Args:
            user_id: 用户 ID
        """
        async with self._lock:
            if user_id in self._sandboxes:
                del self._sandboxes[user_id]
                logger.info("sandbox_pool.cleanup", user_id=user_id)

    async def cleanup_idle(self, max_idle: float = None):
        """清理空闲沙箱

        Args:
            max_idle: 最大空闲秒数，默认使用配置的 idle_timeout
        """
        if max_idle is None:
            max_idle = self._idle_timeout

        cutoff = time.time() - max_idle

        async with self._lock:
            to_remove = [
                uid for uid, sb in self._sandboxes.items()
                if sb.last_used_at < cutoff
            ]
            for uid in to_remove:
                del self._sandboxes[uid]

            if to_remove:
                logger.info("sandbox_pool.cleanup_idle", removed=len(to_remove))

    # === 统计 ===

    @property
    def pool_size(self) -> int:
        """当前池大小"""
        return len(self._sandboxes)

    @property
    def stats(self) -> dict:
        """池统计信息"""
        return {
            "pool_size": self.pool_size,
            "max_size": self._max_size,
            "idle_timeout": self._idle_timeout,
            "is_warming": self._is_warming,
            "users": list(self._sandboxes.keys()),
        }


# === 全局单例 ===

_pool: SandboxPool | None = None


def get_sandbox_pool() -> SandboxPool:
    """获取全局沙箱池单例"""
    global _pool
    if _pool is None:
        _pool = SandboxPool()
    return _pool
