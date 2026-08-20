"""Task Tool - Subagent 任务委派工具

主 Agent 调用的 task 工具，用于创建 Subagent 实例并执行任务。
支持并行执行和特殊化配置。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Literal

import structlog

from ai_agent.agents.subagent import Subagent, TaskExecutor, get_task_executor
from ai_agent.exception.exceptions import ToolExecutionError
from ai_agent.schemas.task import (
    ParallelTaskInput,
    ParallelTaskOutput,
    SubagentConfig,
    TaskInput,
    TaskOutput,
    TaskResult,
    TaskStatus,
)

logger = structlog.get_logger(__name__)


# === Task Tool for Main Agent ===

async def task_tool(
    task_id: str | None = None,
    task_type: str = "general",
    description: str = "",
    params: dict[str, Any] | None = None,
    config: SubagentConfig | None = None,
) -> str:
    """Task Tool - 创建并执行 Subagent 任务

    主 Agent 调用此工具创建独立的 Subagent 实例来执行任务。

    Args:
        task_id: 任务标识符，不指定则自动生成
        task_type: 任务类型，如 'research', 'coding', 'review', 'general'
        description: 任务描述
        params: 任务参数字典
        config: Subagent 特殊化配置

    Returns:
        str: JSON 格式的任务输出报告
    """
    if not description:
        raise ToolExecutionError("task_tool", "description is required")

    # 生成任务 ID
    tid = task_id or f"task-{uuid.uuid4().hex[:8]}"

    # 构建任务输入
    task_input = TaskInput(
        task_id=tid,
        task_type=task_type,
        description=description,
        params=params or {},
        config=config or SubagentConfig(),
    )

    # 创建 Subagent 并执行
    subagent = Subagent()
    result = await subagent.execute(task_input)

    logger.info(
        "task_tool.execute",
        task_id=tid,
        task_type=task_type,
        status=result.status.value,
    )

    # 返回 JSON 报告
    return json.dumps(
        {
            "task_id": result.task_id,
            "status": result.status.value,
            "result": result.result,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
            "summary": result.summary,
        },
        ensure_ascii=False,
        indent=2,
    )


async def parallel_task_tool(
    tasks: list[dict],
    max_concurrency: int | None = None,
) -> str:
    """Parallel Task Tool - 并行执行多个 Subagent 任务

    主 Agent 调用此工具并行创建多个 Subagent 实例来执行任务。

    Args:
        tasks: 任务列表，每个任务是一个字典，包含：
            - task_id: 任务标识符（可选）
            - task_type: 任务类型（默认 'general'）
            - description: 任务描述（必填）
            - params: 任务参数（可选）
            - config: Subagent 配置（可选）
        max_concurrency: 最大并发数（可选）

    Returns:
        str: JSON 格式的批量任务输出报告
    """
    if not tasks:
        raise ToolExecutionError("parallel_task_tool", "tasks cannot be empty")

    # 构建任务输入列表
    task_inputs = []
    for i, task_dict in enumerate(tasks):
        task_id = task_dict.get("task_id") or f"task-{uuid.uuid4().hex[:8]}"
        config_dict = task_dict.get("config", {})
        config = SubagentConfig(**config_dict) if config_dict else SubagentConfig()

        task_input = TaskInput(
            task_id=task_id,
            task_type=task_dict.get("task_type", "general"),
            description=task_dict.get("description", ""),
            params=task_dict.get("params", {}),
            config=config,
        )
        task_inputs.append(task_input)

    # 创建执行器并执行
    executor = TaskExecutor(max_concurrency=max_concurrency)
    started_at = datetime.now()
    results = await executor.execute_parallel(task_inputs)
    completed_at = datetime.now()

    # 构建输出
    output = ParallelTaskOutput(
        results=results,
        started_at=started_at,
        completed_at=completed_at,
    )

    # 生成汇总报告
    task_results = TaskResult(tasks=results)

    logger.info(
        "parallel_task_tool.execute",
        total=len(tasks),
        success=task_results.success_count,
        failed=task_results.failed_count,
    )

    return json.dumps(
        {
            "total": task_results.total_count,
            "success": task_results.success_count,
            "failed": task_results.failed_count,
            "total_duration_seconds": output.total_duration_seconds,
            "summary_report": task_results.summary_report,
            "results": [
                {
                    "task_id": r.task_id,
                    "status": r.status.value,
                    "result": r.result,
                    "error": r.error,
                    "duration_seconds": r.duration_seconds,
                    "summary": r.summary,
                }
                for r in results
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


# === Tool Definitions for LangGraph ===

def get_task_tools() -> list[dict]:
    """获取 Task Tool 定义（用于 LangGraph Tool Calling）

    Returns:
        list[dict]: 工具定义列表
    """
    return [
        {
            "name": "task",
            "description": """创建独立的 Subagent 实例来执行任务。

主要 Agent 调用此工具将复杂任务委派给专业的 Subagent。
每个 Subagent 拥有独立上下文，执行完毕返回单个报告。

使用场景：
- 复杂任务分解并行处理
- 需要不同专业能力的任务
- 需要同时执行多个独立任务

参数：
- task_id: 任务标识符（可选，自动生成）
- task_type: 任务类型（research/coding/review/general）
- description: 任务描述（必填）
- params: 任务参数字典（可选）
- config: Subagent 配置（可选，包含 model/temperature/system_prompt 等）""",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "任务标识符，不指定则自动生成",
                    },
                    "task_type": {
                        "type": "string",
                        "enum": ["research", "coding", "review", "general"],
                        "description": "任务类型",
                        "default": "general",
                    },
                    "description": {
                        "type": "string",
                        "description": "任务描述（必填）",
                    },
                    "params": {
                        "type": "object",
                        "description": "任务参数",
                        "additionalProperties": True,
                    },
                    "config": {
                        "type": "object",
                        "description": "Subagent 特殊化配置",
                        "properties": {
                            "model": {"type": "string"},
                            "temperature": {"type": "number"},
                            "max_tokens": {"type": "integer"},
                            "system_prompt": {"type": "string"},
                            "timeout_seconds": {"type": "integer"},
                        },
                    },
                },
                "required": ["description"],
            },
        },
        {
            "name": "parallel_task",
            "description": """并行创建多个 Subagent 实例来同时执行任务。

主 Agent 调用此工具并行执行多个独立任务。
所有任务同时执行，最后返回汇总报告。

使用场景：
- 需要同时执行多个独立任务
- 任务之间没有依赖关系
- 加快处理速度

参数：
- tasks: 任务列表（必填），每个任务包含：
  - task_id: 任务标识符（可选）
  - task_type: 任务类型（可选，默认 general）
  - description: 任务描述（必填）
  - params: 任务参数（可选）
  - config: Subagent 配置（可选）
- max_concurrency: 最大并发数（可选）""",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "任务列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string"},
                                "task_type": {
                                    "type": "string",
                                    "enum": ["research", "coding", "review", "general"],
                                },
                                "description": {"type": "string"},
                                "params": {"type": "object"},
                                "config": {
                                    "type": "object",
                                    "properties": {
                                        "model": {"type": "string"},
                                        "temperature": {"type": "number"},
                                        "max_tokens": {"type": "integer"},
                                        "system_prompt": {"type": "string"},
                                        "timeout_seconds": {"type": "integer"},
                                    },
                                },
                            },
                            "required": ["description"],
                        },
                    },
                    "max_concurrency": {
                        "type": "integer",
                        "description": "最大并发数（可选）",
                    },
                },
                "required": ["tasks"],
            },
        },
    ]


# === Async Task Execution Utilities ===

async def execute_tasks_sync(
    tasks: list[TaskInput],
    max_concurrency: int | None = None,
) -> TaskResult:
    """同步执行任务列表（等待所有任务完成）

    Args:
        tasks: 任务输入列表
        max_concurrency: 最大并发数

    Returns:
        TaskResult: 任务结果
    """
    executor = TaskExecutor(max_concurrency=max_concurrency)
    return await executor.execute_batch(tasks)


async def execute_tasks_async(
    tasks: list[TaskInput],
    max_concurrency: int | None = None,
) -> list[asyncio.Task]:
    """异步执行任务列表（不等待完成，返回 Task 对象列表）

    Args:
        tasks: 任务输入列表
        max_concurrency: 最大并发数

    Returns:
        list[asyncio.Task]: asyncio.Task 对象列表
    """
    executor = TaskExecutor(max_concurrency=max_concurrency)

    async def execute_and_wrap(task_input: TaskInput) -> TaskOutput:
        return await executor.execute_single(task_input)

    return [asyncio.create_task(execute_and_wrap(task)) for task in tasks]
