"""NovelCraft Exception Hierarchy

遵循编码规范 §2.2 的自定义异常体系
"""
from __future__ import annotations


class NovelCraftError(Exception):
    """NovelCraft 基础异常类"""

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code or "UNKNOWN"
        super().__init__(self.message)


# === 业务异常 ===
class BusinessError(NovelCraftError):
    """业务错误基类"""


class ParameterError(BusinessError):
    """参数错误"""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PARAM_ERROR")


class ResourceNotFoundError(BusinessError):
    """资源不存在"""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} not found: {identifier}", code="NOT_FOUND")


# === AI 异常 ===
class AIError(NovelCraftError):
    """AI 相关错误基类"""


class LLMTimeoutError(AIError):
    """LLM 调用超时"""

    def __init__(self, model: str, timeout: int) -> None:
        super().__init__(
            f"LLM call timeout after {timeout}s for model {model}",
            code="LLM_TIMEOUT",
        )


class LLMParseError(AIError):
    """LLM 输出解析失败"""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Failed to parse LLM output: {reason}", code="LLM_PARSE_ERROR")


class ToolExecutionError(AIError):
    """工具执行失败"""

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(f"Tool '{tool_name}' execution failed: {reason}", code="TOOL_ERROR")


class AgentBudgetExhaustedError(AIError):
    """AI 配额耗尽"""

    def __init__(self, budget_type: str) -> None:
        super().__init__(f"AI budget exhausted: {budget_type}", code="BUDGET_EXHAUSTED")


# === 基础设施异常 ===
class InfraError(NovelCraftError):
    """基础设施错误基类"""


class ConfigurationError(InfraError):
    """配置错误"""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Configuration error: {reason}", code="CONFIG_ERROR")
