"""AI Agent SandBox - 文件操作沙箱

提供安全的文件操作环境，防止恶意操作和误操作。

架构：
- Layer 1: PathGuard - 路径验证
- Layer 2: VirtualFS - 虚拟文件系统
- Layer 3: ContentGuard - 内容扫描
- Layer 4: PolicyGuard - 策略控制
- Layer 5: SkillSandboxLoader - Skill 安全加载
- Layer 6: SandboxMiddleware - HITL 中间件
- Layer 7: SandboxPool - 用户隔离 + 池管理 + 预热
"""
from __future__ import annotations

from ai_agent.sandbox.core.sandbox import FileSandbox
from ai_agent.sandbox.core.context import SandboxContext
from ai_agent.sandbox.guards.path_guard import PathGuard
from ai_agent.sandbox.guards.content_guard import ContentGuard
from ai_agent.sandbox.guards.policy_guard import PolicyGuard
from ai_agent.sandbox.loaders.skill_loader import SkillSandboxLoader
from ai_agent.sandbox.backends.virtual_fs import VirtualFileSystem
from ai_agent.sandbox.middleware.sandbox_middleware import SandboxMiddleware
from ai_agent.sandbox.sandbox_pool import SandboxPool, UserSandbox, get_sandbox_pool

__all__ = [
    "FileSandbox",
    "SandboxContext",
    "PathGuard",
    "ContentGuard",
    "PolicyGuard",
    "SkillSandboxLoader",
    "VirtualFileSystem",
    "SandboxMiddleware",
    "SandboxPool",
    "UserSandbox",
    "get_sandbox_pool",
]
