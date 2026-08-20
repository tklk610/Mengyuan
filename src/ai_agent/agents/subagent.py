"""Subagent Implementation

Subagent 任务委派核心实现：
- 每次调用创建全新 Agent 实例
- 独立上下文
- 执行完返回单个报告
- 支持并行执行和特殊化配置
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Literal

import structlog

from ai_agent.config.settings import settings
from ai_agent.exception.exceptions import ToolExecutionError
from ai_agent.llm.factory import ainvoke_with_timeout, get_llm
from ai_agent.schemas.task import (
    SubagentConfig,
    TaskInput,
    TaskOutput,
    TaskResult,
    TaskStatus,
)

logger = structlog.get_logger(__name__)


# === Default System Prompts for Different Task Types ===

DEFAULT_TASK_PROMPTS: dict[str, str] = {
    "research": """你是一个专业的研究助手。请根据用户提供的任务要求，深入研究并提供详细的分析报告。

要求：
1. 全面收集和分析相关信息
2. 提供有见地的分析和结论
3. 引用可靠的信息来源
4. 结构清晰，逻辑严谨

请以 JSON 格式返回研究报告：
{
    "title": "报告标题",
    "summary": "一句话总结",
    "findings": ["发现1", "发现2", ...],
    "analysis": "详细分析",
    "conclusion": "结论",
    "sources": ["来源1", "来源2", ...]
}""",
    "coding": """你是一个专业的编程助手。请根据用户提供的需求编写代码。

要求：
1. 代码必须遵循最佳实践
2. 完整的错误处理
3. 清晰的注释和文档
4. 符合项目编码规范

请以 JSON 格式返回代码结果：
{
    "language": "编程语言",
    "files": [
        {
            "path": "文件路径",
            "content": "文件内容",
            "description": "文件说明"
        }
    ],
    "explanation": "代码说明",
    "tests": ["测试用例"]
}""",
    "review": """你是一个专业的代码审查员。请对提供的代码进行审查。

要求：
1. 检查代码质量和规范遵循
2. 发现潜在 bug 和安全问题
3. 提供改进建议
4. 评估代码可维护性

请以 JSON 格式返回审查结果：
{
    "score": 1-10 的评分,
    "issues": [
        {
            "severity": "critical|major|minor",
            "location": "文件:行号",
            "description": "问题描述",
            "suggestion": "修改建议"
        }
    ],
    "summary": "总体评价",
    "recommendations": ["建议1", "建议2", ...]
}""",
    "general": """你是一个专业的 AI 助手。请根据用户的要求完成任务。

请以 JSON 格式返回结果：
{
    "result": "执行结果",
    "details": {},
    "message": "补充说明"
}""",
}


class Subagent:
    """Subagent 实例

    每次创建都是全新的 Agent 实例，拥有独立上下文。
    """

    def __init__(self, subagent_id: str | None = None):
        """初始化 Subagent 实例

        Args:
            subagent_id: Subagent 唯一标识，不指定则自动生成
        """
        self.subagent_id = subagent_id or str(uuid.uuid4())[:8]
        self._context: dict[str, Any] = {}
        self._created_at = datetime.now()

    @property
    def context(self) -> dict[str, Any]:
        """获取独立上下文"""
        return self._context

    def set_context(self, key: str, value: Any) -> None:
        """设置上下文变量"""
        self._context[key] = value

    def clear_context(self) -> None:
        """清空上下文"""
        self._context.clear()

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """执行任务

        Args:
            task_input: 任务输入

        Returns:
            TaskOutput: 任务输出（单个报告）
        """
        task_id = task_input.task_id
        started_at = datetime.now()

        try:
            logger.info(
                "subagent.execute.start",
                subagent_id=self.subagent_id,
                task_id=task_id,
                task_type=task_input.task_type,
            )

            # 获取系统提示词
            system_prompt = self._get_system_prompt(task_input)

            # 构建用户消息
            user_message = self._build_user_message(task_input)

            # 获取 LLM 配置
            llm_config = self._get_llm_config(task_input.config)

            # 调用 LLM
            response = await ainvoke_with_timeout(
                llm_config["llm"],
                f"{system_prompt}\n\n用户任务：{user_message}",
                timeout=task_input.config.timeout_seconds or 120,
            )

            # 解析结果
            result = self._parse_response(response["content"], task_input.task_type)

            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            logger.info(
                "subagent.execute.success",
                subagent_id=self.subagent_id,
                task_id=task_id,
                duration=duration,
            )

            return TaskOutput(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                subagent_id=self.subagent_id,
                model_used=llm_config["model"],
            )

        except Exception as e:
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            logger.error(
                "subagent.execute.failed",
                subagent_id=self.subagent_id,
                task_id=task_id,
                error=str(e),
            )

            return TaskOutput(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                subagent_id=self.subagent_id,
            )

    def _get_system_prompt(self, task_input: TaskInput) -> str:
        """获取系统提示词"""
        if task_input.config.system_prompt:
            return task_input.config.system_prompt

        return DEFAULT_TASK_PROMPTS.get(
            task_input.task_type,
            DEFAULT_TASK_PROMPTS["general"],
        )

    def _build_user_message(self, task_input: TaskInput) -> str:
        """构建用户消息"""
        lines = [
            f"任务描述：{task_input.description}",
            "",
        ]

        if task_input.params:
            lines.append("任务参数：")
            for key, value in task_input.params.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        return "\n".join(lines)

    def _get_llm_config(self, config: SubagentConfig) -> dict:
        """获取 LLM 配置"""
        llm_kwargs = {}

        if config.model:
            # 解析模型名称，提取 provider
            if "/" in config.model:
                provider = config.model.split("/")[0]
                model_name = config.model
            else:
                provider = "openai"
                model_name = config.model
            llm_kwargs["model"] = model_name

        if config.temperature is not None:
            llm_kwargs["temperature"] = config.temperature

        if config.max_tokens is not None:
            llm_kwargs["max_tokens"] = config.max_tokens

        llm = get_llm(**llm_kwargs)
        model_name = config.model or settings.openai_model

        return {"llm": llm, "model": model_name}

    def _parse_response(self, content: str, task_type: str) -> dict:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            return json.loads(json_str.strip())
        except json.JSONDecodeError:
            # 如果不是 JSON，返回原始内容
            return {
                "raw_content": content,
                "task_type": task_type,
            }


# === Task Executor with Parallel Support ===

class TaskExecutor:
    """任务执行器

    支持并行执行多个 Subagent 任务
    """

    def __init__(self, max_concurrency: int | None = None):
        """初始化任务执行器

        Args:
            max_concurrency: 最大并发数，None 表示无限制
        """
        self._max_concurrency = max_concurrency
        self._semaphore: asyncio.Semaphore | None = None
        if max_concurrency:
            self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_single(self, task_input: TaskInput) -> TaskOutput:
        """执行单个任务

        Args:
            task_input: 任务输入

        Returns:
            TaskOutput: 任务输出
        """
        subagent = Subagent()
        return await subagent.execute(task_input)

    async def execute_parallel(self, tasks: list[TaskInput]) -> list[TaskOutput]:
        """并行执行多个任务

        Args:
            tasks: 任务列表

        Returns:
            list[TaskOutput]: 所有任务的结果
        """
        if self._semaphore:
            async def bounded_execute(task: TaskInput) -> TaskOutput:
                async with self._semaphore:
                    return await self.execute_single(task)

            results = await asyncio.gather(
                *[bounded_execute(task) for task in tasks],
                return_exceptions=True,
            )
        else:
            results = await asyncio.gather(
                *[self.execute_single(task) for task in tasks],
                return_exceptions=True,
            )

        # 处理异常结果
        outputs = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                outputs.append(
                    TaskOutput(
                        task_id=tasks[i].task_id,
                        status=TaskStatus.FAILED,
                        error=str(result),
                    )
                )
            else:
                outputs.append(result)

        return outputs

    async def execute_batch(self, tasks: list[TaskInput]) -> TaskResult:
        """批量执行任务

        Args:
            tasks: 任务列表

        Returns:
            TaskResult: 批量任务结果
        """
        outputs = await self.execute_parallel(tasks)
        return TaskResult(tasks=outputs)


# === Global Executor Instance ===
_executor: TaskExecutor | None = None


def get_task_executor(max_concurrency: int | None = None) -> TaskExecutor:
    """获取全局任务执行器单例

    Args:
        max_concurrency: 最大并发数

    Returns:
        TaskExecutor 实例
    """
    global _executor
    if _executor is None:
        _executor = TaskExecutor(max_concurrency=max_concurrency)
    return _executor
