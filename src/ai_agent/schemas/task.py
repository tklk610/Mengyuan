"""Task Schema Definitions

Subagent 任务委派相关的 Pydantic 模型定义
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, NotRequired

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubagentConfig(BaseModel):
    """Subagent 特殊化配置

    每个 Subagent 实例的独立配置，支持特殊化设置。
    """

    # 模型配置
    model: str | None = None
    """指定使用的模型，如 openai/gpt-4o-mini，不指定则使用默认模型"""

    temperature: float | None = None
    """采样温度，0.0-2.0，不指定则使用默认值"""

    max_tokens: int | None = None
    """最大输出 token 数，不指定则使用默认值"""

    # 系统提示词配置
    system_prompt: str | None = None
    """自定义系统提示词，不指定则使用默认提示词"""

    # 超时配置
    timeout_seconds: int | None = None
    """任务执行超时时间（秒），不指定则使用默认值"""

    # 特殊化选项
    tools: list[str] | None = None
    """允许使用的工具列表，None 表示使用所有工具"""

    memory_enabled: bool = True
    """是否启用记忆功能"""

    class Config:
        frozen = False


class TaskInput(BaseModel):
    """任务输入定义"""

    task_id: str = Field(..., description="唯一任务标识符")
    task_type: str = Field(..., description="任务类型，如 'research', 'coding', 'review'")
    description: str = Field(..., description="任务描述")

    # 任务参数
    params: dict[str, Any] = Field(default_factory=dict, description="任务参数")

    # Subagent 配置
    config: SubagentConfig = Field(default_factory=SubagentConfig, description="Subagent 配置")

    # 执行控制
    parallel: bool = Field(default=False, description="是否支持并行执行")
    priority: int = Field(default=0, description="任务优先级，数值越大优先级越高")


class TaskOutput(BaseModel):
    """任务输出定义

    Subagent 执行完毕后返回的报告
    """

    task_id: str = Field(..., description="任务标识符")
    status: TaskStatus = Field(..., description="任务状态")

    # 执行结果
    result: dict[str, Any] | None = Field(default=None, description="任务执行结果")
    error: str | None = Field(default=None, description="错误信息")

    # 执行统计
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")
    duration_seconds: float | None = Field(default=None, description="执行耗时（秒）")

    # Subagent 信息
    subagent_id: str | None = Field(default=None, description="执行的 Subagent ID")
    model_used: str | None = Field(default=None, description="使用的模型")

    @property
    def is_success(self) -> bool:
        """是否成功完成"""
        return self.status == TaskStatus.COMPLETED

    @property
    def summary(self) -> str:
        """返回单个报告摘要"""
        if self.is_success:
            return f"✅ Task {self.task_id} completed successfully in {self.duration_seconds:.2f}s"
        return f"❌ Task {self.task_id} failed: {self.error}"


class TaskResult(BaseModel):
    """任务结果（用于批量任务）"""

    tasks: list[TaskOutput] = Field(default_factory=list, description="任务结果列表")

    @property
    def total_count(self) -> int:
        """总任务数"""
        return len(self.tasks)

    @property
    def success_count(self) -> int:
        """成功任务数"""
        return sum(1 for t in self.tasks if t.is_success)

    @property
    def failed_count(self) -> int:
        """失败任务数"""
        return sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)

    @property
    def summary_report(self) -> str:
        """生成汇总报告"""
        lines = [
            f"📊 Task Execution Report",
            f"Total: {self.total_count} | ✅ Success: {self.success_count} | ❌ Failed: {self.failed_count}",
            "",
        ]
        for task in self.tasks:
            lines.append(f"  {task.summary}")
        return "\n".join(lines)


class ParallelTaskInput(BaseModel):
    """并行任务输入"""

    tasks: list[TaskInput] = Field(..., description="任务列表")
    wait_for_all: bool = Field(default=True, description="是否等待所有任务完成")
    max_concurrency: int | None = Field(default=None, description="最大并发数，None 表示无限制")


class ParallelTaskOutput(BaseModel):
    """并行任务输出"""

    results: list[TaskOutput] = Field(default_factory=list, description="所有任务结果")
    started_at: datetime = Field(default_factory=datetime.now, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")

    @property
    def total_duration_seconds(self) -> float | None:
        """总执行耗时"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
