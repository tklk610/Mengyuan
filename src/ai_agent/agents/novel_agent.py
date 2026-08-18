"""NovelCraft Deep Agents 配置

PoC 版本的 Deep Agents 配置，包含:
- Narrator Agent (剧情规划)
- Scribe Agent (续写执行)
- HITL 中断机制
"""
from __future__ import annotations

import json
from typing import Literal

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, interrupt

from ai_agent.agents.state import NovelState
from ai_agent.config.settings import settings
from ai_agent.exception.exceptions import ToolExecutionError
from ai_agent.llm.factory import ainvoke_with_timeout, get_llm
from ai_agent.prompts.loader import prompt_loader

logger = structlog.get_logger(__name__)


def _build_checkpointer():
    """构建 checkpointer：生产用 Redis，本地无 Redis 时降级到 MemorySaver"""
    if settings.redis_url:
        try:
            checkpointer = RedisSaver(redis_url=settings.redis_url)
            checkpointer.setup()  # 初始化 Redis 连接
            return checkpointer
        except Exception as e:
            logger.warning("redis_checkpointer.fallback", reason=str(e))
    return MemorySaver()


# === Helper Functions ===

async def call_llm(prompt: str, system_prompt: str | None = None) -> str:
    """调用 LLM 的辅助函数

    Args:
        prompt: 用户 prompt
        system_prompt: 系统 prompt

    Returns:
        LLM 输出内容
    """
    try:
        llm = get_llm(temperature=0.7)
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = await ainvoke_with_timeout(llm, full_prompt, timeout=120)
        return response["content"]
    except Exception as e:
        logger.error("llm.call.failed", error=str(e))
        raise ToolExecutionError("llm_call", str(e)) from e


# === Agent Nodes ===

async def narrator_node(state: NovelState) -> dict:
    """Narrator Agent Node - 生成大纲

    Args:
        state: 当前状态

    Returns:
        更新状态的部分字典
    """
    logger.info("narrator.start", user_request=state["user_request"], genre=state["genre"])

    # 加载 Narrator prompt
    narrator_template = prompt_loader.load("narrator_system", version=1)
    genre_guide = prompt_loader.load_genre_guide(state["genre"])

    # 渲染 prompt
    prompt = narrator_template["template"].replace("{{genre}}", state["genre"])
    prompt = prompt.replace("{{genre_style_guide}}", genre_guide)

    # 调用 LLM
    response = await call_llm(prompt)

    # 解析 JSON 响应
    try:
        # 尝试提取 JSON 部分
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]

        outline_data = json.loads(json_str.strip())

        logger.info("narrator.complete", title=outline_data.get("title", ""))

        return {
            "outline": outline_data.get("outline", {}),
            "characters": outline_data.get("characters", {}),
            "phase": "planning_complete",
            "messages": [
                {"role": "assistant", "content": f"📋 大纲已生成：{outline_data.get('title', '未命名')}"}
            ],
        }
    except json.JSONDecodeError as e:
        logger.error("narrator.parse.failed", error=str(e), response=response[:200])
        raise ToolExecutionError("narrator", f"Failed to parse outline JSON: {e}") from e


async def scribe_node(state: NovelState) -> Command:
    """Scribe Agent Node - 生成正文

    HITL 机制：
    1. 首次执行：生成 draft → interrupt(draft_info) 暂停
    2. interrupt() 返回 None，checkpoint 保存 interrupt_value
    3. /api/resume 传入 choice → graph 恢复，interrupt() 返回 choice
    4. 处理 choice（accept/rewrite/restart）

    重入检测：interrupt_value 中的 "was_interrupted" 标记，
    由 interrupt() 的返回值（用户选择）提供。

    Args:
        state: 当前状态

    Returns:
        Command 对象，包含更新和路由
    """
    logger.info("scribe.start", current_chapter=state["current_chapter"])

    chapter_num = state["current_chapter"]

    # === 检查是否为重入（interrupt 已触发，等待用户选择）===
    # 通过 interrupt_value["was_interrupted"] 判断（该标记由 interrupt() 首次调用时设
    # 并通过 interrupt checkpoint 持久化，重入时由 LangGraph 注入到 interrupt() 返回值中）
    interrupt_val = state.get("interrupt_value")
    if interrupt_val and interrupt_val.get("was_interrupted"):
        # 重入：draft 已保存在 interrupt_value 中，直接获取
        draft = interrupt_val.get("draft", "")
        choice = interrupt_val.get("choice", "accept")
        logger.info("scribe.resume", choice=choice, chapter=chapter_num)
    else:
        # === 首次执行：生成 draft，然后中断 ===
        scribe_template = prompt_loader.load("scribe_system", version=1)
        genre_guide = prompt_loader.load_genre_guide(state["genre"])

        outline = state.get("outline") or {}

        # 找到当前章节的信息
        chapter_info: dict | None = None
        for act_key in ["act1", "act2", "act3"]:
            act_data = outline.get(act_key, {})
            for ch in act_data.get("chapters", []):
                if ch.get("ch_num") == chapter_num:
                    chapter_info = ch
                    break
            if chapter_info:
                break

        if not chapter_info:
            chapter_info = {"ch_num": chapter_num, "title": f"第{chapter_num}章", "summary": "续写"}

        # 渲染 prompt
        prompt = scribe_template["template"]
        prompt = prompt.replace("{{chapter_number}}", str(chapter_num))
        prompt = prompt.replace("{{chapter_title}}", chapter_info.get("title", f"第{chapter_num}章"))
        prompt = prompt.replace("{{outline_json}}", json.dumps(outline, ensure_ascii=False, indent=2))
        prompt = prompt.replace("{{genre_style}}", genre_guide)
        prompt = prompt.replace("{{context_window}}", state.get("context_window", "（无上下文）"))

        # 调用 LLM 生成正文
        response = await call_llm(prompt)
        draft = response.replace("---END---", "").strip()
        logger.info("scribe.complete", word_count=len(draft))

        # === HITL 中断 ===
        # 中断的 checkpoint 会保存 interrupt_value，重入时该值作为 interrupt() 的返回值
        # 若 interrupt_value["was_interrupted"] == True，说明是重入（choice 已确定）
        interrupt_value = {
            "draft": draft,
            "options": ["accept", "rewrite", "restart"],
            "message": "请审阅本章草稿",
            "chapter": chapter_num,
            "was_interrupted": True,  # 首次中断，标记重入时应从此值判断
        }
        # 将 interrupt_value 写入 state，确保它被 checkpoint 持久化
        state["interrupt_value"] = interrupt_value
        choice = interrupt(interrupt_value)
        # choice 永不为 None（重入时 interrupt 返回用户选择的值）
        if choice is None:
            raise ToolExecutionError("scribe", "interrupt returned None unexpectedly")

    # === 处理用户选择 ===
    # interrupt() 返回的是 Command(resume={...}) 的完整字典，
    # 其中 "choice" 字段才是用户选择的字符串（accept/rewrite/restart）
    user_choice = choice.get("choice") if isinstance(choice, dict) else choice
    if user_choice == "accept":
        return Command(
            update={
                "draft": draft,
                "phase": "complete",
                "messages": [{"role": "assistant", "content": f"✅ 第{chapter_num}章已完成"}],
                "interrupt_options": None,
                "interrupt_value": None,
            },
            goto=END,
        )
    elif user_choice == "rewrite":
        return Command(
            update={
                "draft": None,
                "phase": "writing",
                "messages": [{"role": "assistant", "content": "🔄 正在重新生成..."}],
                "interrupt_options": None,
                "interrupt_value": None,
            },
            goto="scribe",
        )
    else:  # restart
        return Command(
            update={
                "outline": None,
                "characters": None,
                "draft": None,
                "current_chapter": 1,
                "phase": "idle",
                "messages": [{"role": "assistant", "content": "🔄 开始新创作..."}],
                "interrupt_options": None,
                "interrupt_value": None,
            },
            goto=END,
        )


def _router(state: NovelState) -> Literal["narrator", "scribe", "__end__"]:
    """路由函数 — 根据当前状态决定下一步（不修改状态）"""
    if state.get("phase") == "idle" and not state.get("outline"):
        return "narrator"
    elif state.get("outline") and not state.get("draft"):
        return "scribe"
    else:
        return "__end__"


# === Build Graph ===

def build_novel_graph(*, checkpointer=None, store=None):
    """构建 NovelCraft Agent Graph

    Args:
        checkpointer: 可选；不传则自动通过 _build_checkpointer() 创建。
                      测试时传入同一个 checkpointer 实例即可验证跨 graph 重启的状态恢复。
        store: 可选；不传则默认 InMemoryStore()。
    Returns:
        编译后的 LangGraph
    """
    if checkpointer is None:
        checkpointer = _build_checkpointer()
    if store is None:
        store = InMemoryStore()

    builder = StateGraph(NovelState)

    # 添加节点
    builder.add_node("narrator", narrator_node)
    builder.add_node("scribe", scribe_node)

    # START → 条件路由
    builder.add_conditional_edges(
        START,
        _router,
        {
            "narrator": "narrator",
            "scribe": "scribe",
            "__end__": END,
        },
    )

    # narrator / scribe 执行完后回到路由器重新判断
    builder.add_conditional_edges(
        "narrator",
        _router,
        {
            "narrator": "narrator",
            "scribe": "scribe",
            "__end__": END,
        },
    )

    # scribe 执行完后直接结束（由 interrupt 控制流程）
    builder.add_edge("scribe", END)

    # 编译
    graph = builder.compile(checkpointer=checkpointer, store=store)

    checkpointer_name = (
        "RedisSaver" if isinstance(checkpointer, RedisSaver) else "MemorySaver"
    )
    logger.info("novel_graph.built", checkpointer=checkpointer_name)
    return graph


# === Global Graph Instance ===
novel_graph = build_novel_graph()
