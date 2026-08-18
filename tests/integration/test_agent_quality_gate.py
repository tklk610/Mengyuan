"""Agent 集成测试样例：AI Agent 提交代码 -> 红线门禁扫描 -> 通过/拒绝。

本测试是『端到端』集成样例，覆盖：
    1. Agent (模拟为 LangGraph StateGraph + tool) 提交一份变更
    2. CI 流水线调用 scripts/check_red_lines.py 做红线扫描
    3. 期望：
        - 含 R10 f-string 注入违规的代码 -> 红线扫描拒绝
        - 干净的代码 -> 红线扫描通过

是『质量门禁 (quality gate)』与『Agent 工作流』协同的代表性样例。
未来真实 Agent 接入时，只需替换 SimulatedCoderAgent 为真实 Agent。
"""

from __future__ import annotations

import shutil
import subprocess
import sys

# Generator type not needed; fake_repo uses simple return.
from dataclasses import dataclass
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SCANNER = SCRIPTS_DIR / "check_red_lines.py"


@dataclass
class AgentSubmission:
    """模拟 AI Agent 提交到代码库的一份变更。

    Attributes:
        path: 文件相对路径（相对于 src/）
        content: 文件内容
    """

    path: str
    content: str


class SimulatedCoderAgent:
    """模拟 AI Coder Agent（替代真正的 LangGraph Agent）。

    现实集成方式：
        coder = LangGraphAgent.from_config(...)
        submission = coder.generate(feature_request)
    这里用最简单的 dataclass + 静态方法模拟，方便测试。
    """

    @staticmethod
    def submit_clean_change() -> list[AgentSubmission]:
        """生成一份『干净的』提交样例（应通过红线门禁）。"""
        return [
            AgentSubmission(
                path="ai_agent/llm/factory.py",
                content=(
                    "\"\"\"LLM factory - 统一封装超时/重试/token 计数。\"\"\"\n"
                    "from tenacity import retry, stop_after_attempt, wait_exponential\n"
                    "from langchain_openai import ChatOpenAI\n"
                    "from ai_agent.guardrail.token_counter import TokenCounter\n"
                    "\n"
                    "def get_llm(model: str = \"gpt-4o-mini\") -> ChatOpenAI:\n"
                    "    \"\"\"获取 LLM 实例，所有调用都带 timeout + retry。\"\"\"\n"
                    "    return ChatOpenAI(\n"
                    "        model=model,\n"
                    "        timeout=30,\n"
                    "        max_retries=3,\n"
                    "    )\n"
                    "\n"
                    "@retry(\n"
                    "    stop=stop_after_attempt(3),\n"
                    "    wait=wait_exponential(multiplier=1, min=1, max=10),\n"
                    "    reraise=True,\n"
                    ")\n"
                    "async def invoke_with_tracking(\n"
                    "    prompt: str,\n"
                    "    request_id: str,\n"
                    "    model: str = \"gpt-4o-mini\",\n"
                    ") -> str:\n"
                    "    llm = get_llm(model)\n"
                    "    counter = TokenCounter()\n"
                    "    with counter.track(request_id=request_id, model=model):\n"
                    "        resp = await llm.ainvoke(prompt)\n"
                    "    return resp.content\n"
                ),
            ),
        ]

    @staticmethod
    def submit_r10_violation() -> list[AgentSubmission]:
        """生成一份『违反 R10 防注入』的提交样例（应被红线门禁拒绝）。"""
        return [
            AgentSubmission(
                path="ai_agent/service/chat_service.py",
                content=(
                    "async def chat(user_input: str) -> str:\n"
                    "    # 错误示范：直接 f-string 拼接用户输入\n"
                    '    prompt = f"You are a helpful assistant. User said: {user_input}"\n'
                    "    llm = ChatOpenAI(model=\"gpt-4o-mini\", timeout=30)\n"
                    "    resp = await llm.ainvoke(prompt)\n"
                    "    return resp.content\n"
                ),
            ),
        ]

    @staticmethod
    def submit_r1_violation() -> list[AgentSubmission]:
        """生成一份『违反 R1 LLM 必须 timeout』的提交样例。"""
        return [
            AgentSubmission(
                path="ai_agent/llm/no_timeout.py",
                content=(
                    "from langchain_openai import ChatOpenAI\n"
                    "llm = ChatOpenAI(model=\"gpt-4o-mini\")  # 缺 timeout\n"
                ),
            ),
        ]


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """构造一个临时『代码库』，包含 src/ 和 scripts/ 两个目录。

    将 scripts/check_red_lines.py 拷贝到临时目录的 scripts/ 下，
    把 Agent 提交的文件写到 src/ 下，让扫描器可以扫描它们。
    cleanup is handled automatically by pytest tmp_path.
    """
    fake_scripts = tmp_path / "scripts"
    fake_scripts.mkdir()
    shutil.copy(SCANNER, fake_scripts / "check_red_lines.py")
    (tmp_path / "src").mkdir()
    return tmp_path


def _apply_submissions(repo_root: Path, submissions: list[AgentSubmission]) -> None:
    """把 Agent 提交的文件落到 repo_root/src/。"""
    for sub in submissions:
        full = repo_root / "src" / sub.path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(sub.content, encoding="utf-8")


def _run_scanner(repo_root: Path) -> subprocess.CompletedProcess:
    """在临时 repo 下运行红线扫描器，返回 CompletedProcess。"""
    # Windows 上 python 解释器可能不在 PATH，用 sys.executable 更稳
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "check_red_lines.py")],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


@pytest.mark.integration
class TestAgentQualityGateIntegration:
    """[Integration] Agent 提交 -> 红线门禁 -> 期望 pass / fail."""

    def test_clean_submission_should_pass_red_line_scan(
        self,
        fake_repo: Path,
    ) -> None:
        """样例 1: Agent 提交一份干净代码 -> 扫描器应返回 0 违规。"""
        # Arrange
        submissions = SimulatedCoderAgent.submit_clean_change()
        _apply_submissions(fake_repo, submissions)

        # Act
        result = _run_scanner(fake_repo)

        # Assert
        assert result.returncode == 0, (
            f"clean submission should pass, got rc={result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        # 清理后的代码不应有 R10/R1/R3 等错误级违规
        assert "[R10/" not in result.stdout
        assert "[R1/error]" not in result.stdout
        assert "[R3/error]" not in result.stdout
        assert "0 violations" in result.stdout or "0 \u8fdd\u89c4" in result.stdout

    def test_r10_violation_should_be_rejected(
        self,
        fake_repo: Path,
    ) -> None:
        """样例 2: Agent 提交 f-string 注入 -> 扫描器应返回 error。"""
        # Arrange
        submissions = SimulatedCoderAgent.submit_r10_violation()
        _apply_submissions(fake_repo, submissions)

        # Act
        result = _run_scanner(fake_repo)

        # Assert
        assert result.returncode == 1, (
            f"R10 violation should make scanner fail, got rc={result.returncode}\n"
            f"stdout:\n{result.stdout}"
        )
        assert "R10" in result.stdout
        assert "f-string" in result.stdout or "Prompt" in result.stdout

    def test_r1_violation_should_be_rejected(
        self,
        fake_repo: Path,
    ) -> None:
        """样例 3: Agent 提交缺 timeout 的 LLM 调用 -> 扫描器应拒绝。"""
        # Arrange
        submissions = SimulatedCoderAgent.submit_r1_violation()
        _apply_submissions(fake_repo, submissions)

        # Act
        result = _run_scanner(fake_repo)

        # Assert
        assert result.returncode == 1
        assert "R1" in result.stdout
        assert "timeout" in result.stdout.lower()

    def test_multiple_violations_should_be_reported_individually(
        self,
        fake_repo: Path,
    ) -> None:
        """样例 4: 多条违规应被分别报告（不互相覆盖）。"""
        submissions = (
            SimulatedCoderAgent.submit_r1_violation()
            + SimulatedCoderAgent.submit_r10_violation()
        )
        _apply_submissions(fake_repo, submissions)

        result = _run_scanner(fake_repo)

        assert result.returncode == 1
        assert "R1" in result.stdout
        assert "R10" in result.stdout

    def test_scanner_should_be_invokable_from_any_cwd(
        self,
        fake_repo: Path,
    ) -> None:
        """样例 5: 从其他目录调用扫描器也应正确工作（脚本相对路径处理）。"""
        # 让 Agent 提交一份干净代码
        _apply_submissions(fake_repo, SimulatedCoderAgent.submit_clean_change())

        # 从一个完全无关的目录运行
        unrelated_dir = fake_repo.parent / "unrelated"
        unrelated_dir.mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(fake_repo / "scripts" / "check_red_lines.py")],
            cwd=str(unrelated_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout
