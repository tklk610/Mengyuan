"""DeepAgent-based NovelCraft Agent

使用 DeepAgent 架构重构的 NovelCraft Agent：
- create_deep_agent() 创建主 Agent
- Middleware 配置（TodoList/Filesystem/SubAgent/HITL/Skills/Memory）
- Subagents: Narrator, Scribe, Stylist
"""
from __future__ import annotations

import os
from typing import Any, Literal

import structlog

logger = structlog.get_logger(__name__)

# 延迟导入 deepagents（避免包兼容性问题）
_deep_agent_imported = False
_create_deep_agent = None
_FilesystemBackend = None


def _ensure_deepagents_imported():
    """确保 deepagents 已导入（延迟导入模式）"""
    global _deep_agent_imported, _create_deep_agent, _FilesystemBackend
    if not _deep_agent_imported:
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.store.memory import InMemoryStore
        from deepagents import create_deep_agent
        from deepagents.backends import FilesystemBackend

        _create_deep_agent = create_deep_agent
        _FilesystemBackend = FilesystemBackend
        _deep_agent_imported = True


# === Subagent Definitions ===

def _create_narrator_subagent():
    """创建 Narrator Subagent - 负责大纲规划"""
    from langchain_core.tools import tool

    @tool
    def plan_outline(genre: str, user_request: str) -> str:
        """根据用户需求和题材规划小说大纲。

        Args:
            genre: 小说题材（仙侠/都市/科幻等）
            user_request: 用户原始需求

        Returns:
            JSON 格式的大纲，包含 title/outline/characters
        """
        # 这里会调用 LLM 生成大纲
        from ai_agent.agents.novel_agent import call_llm
        from ai_agent.prompts.loader import prompt_loader

        narrator_template = prompt_loader.load("narrator_system", version=1)
        genre_guide = prompt_loader.load_genre_guide(genre)

        prompt = narrator_template["template"].replace("{{genre}}", genre)
        prompt = prompt.replace("{{genre_style_guide}}", genre_guide)

        return call_llm(prompt)

    return {
        "name": "narrator",
        "description": "专业的小说大纲规划师，负责根据用户需求生成故事结构、角色设定和大纲",
        "system_prompt": """你是一个专业的小说架构师。

你的职责是根据用户的需求规划完整的小说大纲。
你需要：
1. 分析用户需求，确定故事类型和风格
2. 设计故事结构（起承转合）
3. 创建主要角色设定
4. 规划章节大纲

请以结构化 JSON 格式返回大纲。""",
        "tools": [plan_outline],
    }


def _create_scribe_subagent():
    """创建 Scribe Subagent - 负责正文写作"""
    from langchain_core.tools import tool

    @tool
    def write_chapter(
        chapter_number: int,
        chapter_title: str,
        outline_json: str,
        genre_style: str,
        context_window: str = "",
    ) -> str:
        """根据大纲编写指定章节的正文。

        Args:
            chapter_number: 章节号
            chapter_title: 章节标题
            outline_json: 大纲 JSON 字符串
            genre_style: 题材风格指南
            context_window: 上下文窗口（前文内容）

        Returns:
            章节正文内容
        """
        from ai_agent.agents.novel_agent import call_llm
        from ai_agent.prompts.loader import prompt_loader
        import json

        scribe_template = prompt_loader.load("scribe_system", version=1)
        outline = json.loads(outline_json)

        prompt = scribe_template["template"]
        prompt = prompt.replace("{{chapter_number}}", str(chapter_number))
        prompt = prompt.replace("{{chapter_title}}", chapter_title)
        prompt = prompt.replace("{{outline_json}}", outline_json)
        prompt = prompt.replace("{{genre_style}}", genre_style)
        prompt = prompt.replace("{{context_window}}", context_window)

        response = call_llm(prompt)
        return response.replace("---END---", "").strip()

    return {
        "name": "scribe",
        "description": "专业的小说写作助手，负责根据大纲编写精彩的故事正文",
        "system_prompt": """你是一个专业的小说写作助手。

你的职责是根据给定的大纲编写精彩的故事正文。
你需要：
1. 严格遵循大纲设定的故事线
2. 塑造鲜活的角色形象
3. 使用生动的语言描写场景
4. 控制适当的篇幅和节奏

请确保内容健康向上，不包含敏感内容。""",
        "tools": [write_chapter],
    }


def _create_stylist_subagent():
    """创建 Stylist Subagent - 负责风格控制"""
    from langchain_core.tools import tool

    @tool
    def analyze_style(text_sample: str, genre_hint: str = "") -> str:
        """分析文本样本的风格特征。

        Args:
            text_sample: 文本样本
            genre_hint: 题材提示（可选）

        Returns:
            JSON 格式的风格分析结果
        """
        from ai_agent.agents.stylist_agent import stylist_agent
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        profile = loop.run_until_complete(
            stylist_agent.create_style_profile(
                user_id="system",
                name="temp",
                text_sample=text_sample,
                genre_hint=genre_hint,
            )
        )
        import json
        return json.dumps(profile, ensure_ascii=False)

    return {
        "name": "stylist",
        "description": "专业的风格分析专家，负责分析文本风格并提取风格特征",
        "system_prompt": """你是一个专业的风格分析专家。

你的职责是分析文本样本，提取写作风格特征。
你需要分析：
1. 叙事视角和人称
2. 文字风格（简洁/华丽等）
3. 常用表达和句式
4. 题材特点

请以结构化 JSON 格式返回风格分析结果。""",
        "tools": [analyze_style],
    }


# === Build Deep Agent ===

def build_deep_novel_agent(
    *,
    skills_dir: str | None = None,
    interrupt_on: dict | None = None,
    sandbox_config: dict | None = None,
) -> Any:
    """构建 DeepAgent 架构的 NovelCraft Agent

    Args:
        skills_dir: Skills 目录路径，默认为 ./skills
        interrupt_on: HITL 中断配置，默认为 {"write_chapter": True}
        sandbox_config: 沙箱配置，默认为启用虚拟模式

    Returns:
        DeepAgent 实例
    """
    # 确保 deepagents 已导入
    _ensure_deepagents_imported()

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.store.memory import InMemoryStore
    from ai_agent.config.settings import settings

    # 确定 skills 目录
    if skills_dir is None:
        skills_dir = os.path.join(os.path.dirname(__file__), "..", "..", "skills")

    # 默认沙箱配置
    if sandbox_config is None:
        sandbox_config = {
            "virtual_mode": True,
            "scan_malicious": True,
            "scan_injection": True,
            "scan_sensitive": True,
            "quarantine_suspicious": True,
            "hitl_enabled": True,
        }

    # 创建沙箱（如果配置启用）
    sandbox_backend = None
    if sandbox_config.get("enabled", True):
        from ai_agent.sandbox import FileSandbox

        sandbox_backend = FileSandbox(
            root_dir=".",
            virtual_mode=sandbox_config.get("virtual_mode", True),
            allowed_paths=sandbox_config.get(
                "allowed_paths",
                ["./skills", "./prompts/templates", "./workspace", "./exports"],
            ),
            denied_paths=sandbox_config.get(
                "denied_paths",
                ["./.git", "./.venv", "./src/ai_agent/config"],
            ),
            scan_malicious=sandbox_config.get("scan_malicious", True),
            scan_injection=sandbox_config.get("scan_injection", True),
            scan_sensitive=sandbox_config.get("scan_sensitive", True),
            quarantine_suspicious=sandbox_config.get("quarantine_suspicious", True),
        )
        logger.info(
            "deep_novel_agent.sandbox_enabled",
            virtual_mode=sandbox_config.get("virtual_mode", True),
        )

    # 默认 HITL 配置
    if interrupt_on is None:
        interrupt_on = {
            "write_chapter": True,
        }

    # 构建 subagents 列表
    subagents = [
        _create_narrator_subagent(),
        _create_scribe_subagent(),
        _create_stylist_subagent(),
    ]

    # 系统提示词
    system_prompt = """你是一个专业的小说创作 AI 助手。

你可以帮助用户：
1. 创作小说（仙侠、都市、科幻等多种题材）
2. 规划故事大纲和角色设定
3. 续写故事章节
4. 分析和学习特定写作风格

你有以下专业助手（subagents）可以使用：
- narrator：负责大纲规划和故事结构设计
- scribe：负责具体的章节写作
- stylist：负责风格分析和学习

当用户需要时，你可以委派任务给合适的 subagent。

沙箱保护：
- 所有文件操作都经过安全扫描
- 危险操作需要人工审批
- 敏感信息会被隔离

请始终使用中文与用户交流。"""

    # 使用沙箱作为 backend（如果可用）
    backend = sandbox_backend if sandbox_backend else _FilesystemBackend(
        root_dir=".", virtual_mode=True
    )

    # 创建 DeepAgent
    agent = _create_deep_agent(
        name="NovelCraft",
        model=settings.openai_model,
        system_prompt=system_prompt,
        subagents=subagents,
        skills=[skills_dir] if os.path.exists(skills_dir) else [],
        backend=backend,
        interrupt_on=interrupt_on,
        checkpointer=MemorySaver(),
        store=InMemoryStore(),
    )

    logger.info("deep_novel_agent.built", subagents=len(subagents))
    return agent


# === Global Instance ===
# 注意：由于 deepagents 包的兼容性问题，暂不创建全局实例
# 使用时由调用者自行创建：
#   agent = build_deep_novel_agent()
