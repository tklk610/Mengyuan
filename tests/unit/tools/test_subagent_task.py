"""Unit Tests for Subagent Task Delegation

测试 Subagent 任务委派功能：
- 单个任务执行
- 并行任务执行
- 特殊化配置
- 报告生成
"""
import pytest

from ai_agent.agents.subagent import Subagent, TaskExecutor, get_task_executor
from ai_agent.schemas.task import (
    SubagentConfig,
    TaskInput,
    TaskOutput,
    TaskResult,
    TaskStatus,
)
from ai_agent.tools.subagent_task import (
    task_tool,
    parallel_task_tool,
    get_task_tools,
    execute_tasks_sync,
)


class TestSubagentConfig:
    """SubagentConfig 测试"""

    def test_default_config(self):
        """默认配置"""
        config = SubagentConfig()
        assert config.model is None
        assert config.temperature is None
        assert config.max_tokens is None
        assert config.system_prompt is None
        assert config.timeout_seconds is None
        assert config.memory_enabled is True

    def test_custom_config(self):
        """自定义配置"""
        config = SubagentConfig(
            model="openai/gpt-4o-mini",
            temperature=0.5,
            max_tokens=2000,
            system_prompt="Custom prompt",
            timeout_seconds=60,
        )
        assert config.model == "openai/gpt-4o-mini"
        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        assert config.system_prompt == "Custom prompt"
        assert config.timeout_seconds == 60


class TestTaskInput:
    """TaskInput 测试"""

    def test_task_input_creation(self):
        """创建任务输入"""
        task_input = TaskInput(
            task_id="test-001",
            task_type="research",
            description="研究人工智能的发展趋势",
            params={"focus": "LLM"},
        )
        assert task_input.task_id == "test-001"
        assert task_input.task_type == "research"
        assert task_input.description == "研究人工智能的发展趋势"
        assert task_input.params["focus"] == "LLM"
        assert task_input.parallel is False
        assert task_input.priority == 0

    def test_task_input_defaults(self):
        """默认参数"""
        task_input = TaskInput(
            task_id="test-002",
            task_type="coding",
            description="编写代码",
        )
        assert task_input.params == {}
        assert task_input.config == SubagentConfig()
        assert task_input.parallel is False


class TestTaskOutput:
    """TaskOutput 测试"""

    def test_task_output_success(self):
        """成功任务输出"""
        from datetime import datetime

        output = TaskOutput(
            task_id="test-001",
            status=TaskStatus.COMPLETED,
            result={"data": "test"},
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=1.5,
            subagent_id="sub-001",
            model_used="gpt-4o-mini",
        )
        assert output.is_success is True
        assert "completed successfully" in output.summary

    def test_task_output_failure(self):
        """失败任务输出"""
        output = TaskOutput(
            task_id="test-002",
            status=TaskStatus.FAILED,
            error="Network error",
        )
        assert output.is_success is False
        assert "failed" in output.summary
        assert "Network error" in output.summary


class TestTaskResult:
    """TaskResult 测试"""

    def test_task_result_summary(self):
        """任务结果汇总"""
        from datetime import datetime

        results = TaskResult(
            tasks=[
                TaskOutput(
                    task_id="t1",
                    status=TaskStatus.COMPLETED,
                    duration_seconds=1.0,
                ),
                TaskOutput(
                    task_id="t2",
                    status=TaskStatus.COMPLETED,
                    duration_seconds=2.0,
                ),
                TaskOutput(
                    task_id="t3",
                    status=TaskStatus.FAILED,
                    error="Timeout",
                ),
            ]
        )

        assert results.total_count == 3
        assert results.success_count == 2
        assert results.failed_count == 1

        report = results.summary_report
        assert "Total: 3" in report
        assert "Success: 2" in report
        assert "Failed: 1" in report


class TestSubagent:
    """Subagent 测试"""

    def test_subagent_creation(self):
        """创建 Subagent 实例"""
        subagent = Subagent()
        assert subagent.subagent_id is not None
        assert len(subagent.subagent_id) == 8
        assert subagent.context == {}

    def test_subagent_custom_id(self):
        """自定义 Subagent ID"""
        subagent = Subagent(subagent_id="my-agent")
        assert subagent.subagent_id == "my-agent"

    def test_subagent_context(self):
        """Subagent 上下文"""
        subagent = Subagent()
        subagent.set_context("key1", "value1")
        assert subagent.context["key1"] == "value1"
        subagent.clear_context()
        assert subagent.context == {}


class TestTaskExecutor:
    """TaskExecutor 测试"""

    def test_executor_creation(self):
        """创建执行器"""
        executor = TaskExecutor(max_concurrency=5)
        assert executor._max_concurrency == 5
        assert executor._semaphore is not None

    def test_executor_no_limit(self):
        """无并发限制"""
        executor = TaskExecutor()
        assert executor._max_concurrency is None
        assert executor._semaphore is None

    def test_get_task_executor_singleton(self):
        """获取全局执行器单例"""
        executor1 = get_task_executor()
        executor2 = get_task_executor()
        assert executor1 is executor2


class TestGetTaskTools:
    """Task Tools 定义测试"""

    def test_get_task_tools(self):
        """获取工具定义"""
        tools = get_task_tools()
        assert len(tools) == 2

        tool_names = [t["name"] for t in tools]
        assert "task" in tool_names
        assert "parallel_task" in tool_names

    def test_task_tool_definition(self):
        """Task Tool 定义"""
        tools = get_task_tools()
        task_tool = next(t for t in tools if t["name"] == "task")

        assert "description" in task_tool
        assert "parameters" in task_tool
        assert task_tool["parameters"]["required"] == ["description"]

    def test_parallel_task_tool_definition(self):
        """Parallel Task Tool 定义"""
        tools = get_task_tools()
        parallel_tool = next(t for t in tools if t["name"] == "parallel_task")

        assert "description" in parallel_tool
        assert "parameters" in parallel_tool
        assert "tasks" in parallel_tool["parameters"]["required"]


class TestTaskToolFunction:
    """Task Tool 函数测试"""

    @pytest.mark.asyncio
    async def test_task_tool_requires_description(self):
        """Task Tool 需要描述"""
        with pytest.raises(Exception):
            await task_tool(description="")

    @pytest.mark.asyncio
    async def test_task_tool_basic_call(self):
        """Task Tool 基本调用"""
        import json
        result = await task_tool(
            task_type="general",
            description="简单的测试任务",
        )
        # 由于是 mock LLM，返回可能是失败状态（网络错误）
        assert isinstance(result, str)
        data = json.loads(result)  # 使用 json.loads 解析
        assert "task_id" in data
        assert "status" in data


class TestParallelTaskToolFunction:
    """Parallel Task Tool 函数测试"""

    @pytest.mark.asyncio
    async def test_parallel_task_tool_requires_tasks(self):
        """Parallel Task Tool 需要任务列表"""
        with pytest.raises(Exception):
            await parallel_task_tool(tasks=[])

    @pytest.mark.asyncio
    async def test_parallel_task_tool_basic_call(self):
        """Parallel Task Tool 基本调用"""
        import json
        result = await parallel_task_tool(
            tasks=[
                {
                    "task_type": "general",
                    "description": "任务1",
                },
                {
                    "task_type": "general",
                    "description": "任务2",
                },
            ],
        )
        assert isinstance(result, str)
        data = json.loads(result)
        assert "total" in data
        assert "success" in data
        assert "failed" in data
        assert data["total"] == 2
