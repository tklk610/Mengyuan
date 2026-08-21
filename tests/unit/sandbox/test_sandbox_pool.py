"""Unit Tests for SandboxPool and User Isolation

测试沙箱池和用户隔离功能：
- 用户级沙箱隔离
- 沙箱池管理
- 预热机制
"""
import asyncio
import pytest
import time


class TestSandboxPool:
    """SandboxPool 单元测试"""

    @pytest.mark.asyncio
    async def test_acquire_user_sandbox(self):
        """获取用户沙箱"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool(max_size=5)

        sandbox1 = await pool.acquire("user_1")
        sandbox2 = await pool.acquire("user_2")

        assert sandbox1 is not None
        assert sandbox2 is not None
        assert sandbox1 is not sandbox2  # 不同用户应不同实例

        assert pool.pool_size == 2

    @pytest.mark.asyncio
    async def test_same_user_reuses_sandbox(self):
        """同一用户复用沙箱"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool(max_size=5)

        sandbox1 = await pool.acquire("user_1")
        sandbox2 = await pool.acquire("user_1")

        assert sandbox1 is sandbox2  # 同一用户复用
        assert pool.pool_size == 1

    @pytest.mark.asyncio
    async def test_pool_size_limit(self):
        """池大小限制"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool(max_size=2)

        await pool.acquire("user_1")
        await pool.acquire("user_2")

        # 池已满，第三次获取会触发 LRU 驱逐
        await pool.acquire("user_3")

        assert pool.pool_size <= 2

    @pytest.mark.asyncio
    async def test_eviction_lru(self):
        """LRU 驱逐"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool(max_size=2, idle_timeout=0.1)

        # 用户1、2、3
        await pool.acquire("user_1")
        await asyncio.sleep(0.05)
        await pool.acquire("user_2")
        await asyncio.sleep(0.05)
        await pool.acquire("user_3")

        # user_1 应该被驱逐（最久未使用）
        assert "user_1" not in pool._sandboxes
        assert "user_2" in pool._sandboxes or "user_3" in pool._sandboxes

    @pytest.mark.asyncio
    async def test_warmup(self):
        """预热机制"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool(max_size=5)

        # 先创建沙箱
        await pool.acquire("user_1")
        await pool.acquire("user_2")

        # 预热
        await pool.warmup()

        assert pool._is_warming is False  # 预热完成
        assert pool.stats.get("pool_size") == 2

    @pytest.mark.asyncio
    async def test_cleanup_user(self):
        """清理用户沙箱"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool()

        await pool.acquire("user_1")
        assert pool.pool_size == 1

        await pool.cleanup_user("user_1")
        assert pool.pool_size == 0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """异步上下文管理器用法"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool()

        async with pool.get_sandbox("user_1") as sandbox:
            assert sandbox is not None
            assert pool.pool_size == 1

        # 退出后池中仍有沙箱（release 只更新 last_used_at）
        assert pool.pool_size == 1

    @pytest.mark.asyncio
    async def test_user_isolation(self):
        """用户隔离验证"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool()

        sandbox1 = await pool.acquire("user_1")
        sandbox2 = await pool.acquire("user_2")

        # 用户目录应该不同
        # root_dir 是自动生成的 user_id 路径
        assert sandbox1.root_dir != sandbox2.root_dir

    @pytest.mark.asyncio
    async def test_stats(self):
        """统计信息"""
        from ai_agent.sandbox import SandboxPool

        pool = SandboxPool(max_size=10, idle_timeout=60.0)

        await pool.acquire("user_1")
        await pool.acquire("user_2")

        stats = pool.stats
        assert stats["pool_size"] == 2
        assert stats["max_size"] == 10
        assert stats["idle_timeout"] == 60.0
        assert "user_1" in stats["users"]
        assert "user_2" in stats["users"]

    @pytest.mark.asyncio
    async def test_singleton(self):
        """全局单例"""
        from ai_agent.sandbox import get_sandbox_pool, SandboxPool

        pool1 = get_sandbox_pool()
        pool2 = get_sandbox_pool()

        assert pool1 is pool2


class TestUserSandbox:
    """UserSandbox 单元测试"""

    def test_idle_seconds(self):
        """空闲秒数计算"""
        from ai_agent.sandbox.sandbox_pool import UserSandbox, FileSandbox
        import time

        sandbox = FileSandbox()
        user_sb = UserSandbox(
            user_id="test_user",
            sandbox=sandbox,
            created_at=time.time() - 10.0,
            last_used_at=time.time() - 5.0,
        )

        # idle_seconds 应该 > 5
        assert user_sb.idle_seconds >= 5.0

    def test_touch(self):
        """更新使用时间"""
        from ai_agent.sandbox.sandbox_pool import UserSandbox, FileSandbox

        sandbox = FileSandbox()
        user_sb = UserSandbox(
            user_id="test_user",
            sandbox=sandbox,
            created_at=time.time(),
            last_used_at=time.time(),
            use_count=0,
        )

        old_last_used = user_sb.last_used_at
        time.sleep(0.01)
        user_sb.touch()

        assert user_sb.use_count == 1
        assert user_sb.last_used_at >= old_last_used
