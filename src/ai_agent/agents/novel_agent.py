"""NovelCraft Deep Agents 配置

PoC 版本的 Deep Agents 配置，包含:
- Narrator Agent (剧情规划)
- Scribe Agent (续写执行)
- Stylist Agent (风格控制)
- HITL 中断机制
"""
from __future__ import annotations

import json
from typing import Literal

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, interrupt

from ai_agent.agents.state import NovelState
from ai_agent.config.settings import settings
from ai_agent.exception.exceptions import ToolExecutionError
from ai_agent.llm.factory import ainvoke_with_timeout, get_llm
from ai_agent.prompts.loader import prompt_loader
from ai_agent.tools.subagent_task import task_tool, parallel_task_tool

logger = structlog.get_logger(__name__)


def _get_style_constraints(state: NovelState) -> str:
    """获取风格约束字符串

    Args:
        state: 当前状态

    Returns:
        风格约束字符串，如果无约束则返回空字符串
    """
    style_profile = state.get("style_profile")
    if not style_profile:
        return ""

    characteristics = style_profile.get("characteristics", {})
    banned_words = style_profile.get("banned_words", [])
    sample_phrases = style_profile.get("sample_phrases", [])

    constraints = "\n\n## 风格约束\n"

    if characteristics:
        constraints += "### 写作风格要求：\n"
        for key, value in characteristics.items():
            if value:
                constraints += f"- {key}: {value}\n"

    if banned_words:
        constraints += f"\n### 避免使用的词汇：\n{'、'.join(banned_words)}\n"

    if sample_phrases:
        constraints += f"\n### 典型表达示例：\n{'；'.join(sample_phrases)}\n"

    return constraints


def _build_checkpointer():
    """构建 checkpointer：生产用 Redis，本地无 Redis 时降级到 MemorySaver

    Returns:
        checkpointer 实例（保持与旧测试兼容）
    """
    if settings.redis_url:
        try:
            from langgraph.checkpoint.redis import RedisSaver
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

INTENT_SYSTEM_PROMPT = """你是一个专业的故事创作助手。

分析用户消息，判断其创作意图。

**约束**：
1. 意图必须是中文动词或短语，15字以内
2. 意图必须与故事创作相关（创作/续写/修改/询问/导出等）
3. 不要臆造不存在的意图类型
4. 置信度反映你对判断的确信程度

**参考**（不限于这些，可自由判断）：
- 创作/续写/修改/询问/导出/规划/讨论

**示例**：
- "写个仙侠小说" → {"intent": "故事创作", "confidence": 0.95, "reasoning": "明确请求创作新故事"}
- "继续上次写到哪了" → {"intent": "进度询问", "confidence": 0.9, "reasoning": "询问当前状态"}
- "加个女主角" → {"intent": "角色修改", "confidence": 0.85, "reasoning": "要求修改角色设定"}

输出格式（JSON）：
{
    "intent": "自由判断的意图（中文，15字以内）",
    "confidence": 0.0-1.0之间的置信度,
    "reasoning": "分析理由（20字以内）
}"""


async def intent_node(state: NovelState) -> dict:
    """Intent Agent Node - LLM驱动的意图识别

    Args:
        state: 当前状态

    Returns:
        更新状态的部分字典，包含识别到的意图
    """
    user_message = state.get("user_request", "")
    logger.info("intent.start", user_request=user_message)

    try:
        llm = get_llm(temperature=0.1)
        full_prompt = f"{INTENT_SYSTEM_PROMPT}\n\n用户消息：{user_message}"
        response = await ainvoke_with_timeout(llm, full_prompt, timeout=30)

        # 解析JSON响应
        content = response["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        intent_data = json.loads(content.strip())

        logger.info("intent.complete",
            intent=intent_data.get("intent"),
            confidence=intent_data.get("confidence")
        )

        return {
            "intent": intent_data.get("intent", "new_story"),
            "intent_confidence": intent_data.get("confidence", 0.5),
            "intent_reasoning": intent_data.get("reasoning", ""),
        }

    except Exception as e:
        logger.warning("intent.failed", error=str(e), fallback="new_story")
        # 降级为默认意图
        return {
            "intent": "new_story",
            "intent_confidence": 0.0,
            "intent_reasoning": f"意图识别失败: {str(e)[:20]}",
        }


PLANNER_SYSTEM_PROMPT = """你是一个专业的小说架构师。

根据用户需求，将创作分解为自由的任务图谱。

**约束**：
1. 任务描述中文，50字以内
2. 任务总数不超过10个
3. 估算总字数符合用户需求（默认3000字/章）
4. 依赖关系反映逻辑顺序（无依赖则空列表）
5. story_arc 一句话描述核心故事弧线，30字以内

**可自由设计的任务**：
- 世界观构建、角色设定、场景设计、章节写作、情节发展、修订润色等
- 粒度自由：可以是"第1章"、"主角成长线"、"大纲设计"等
- 支持并行：可并行的任务依赖列表为空

**输出JSON**：
{
    "tasks": [
        {
            "task_id": "任务ID（英文简写）",
            "description": "任务描述（中文，50字以内）",
            "estimated_words": 预估字数,
            "dependencies": ["前置任务ID列表，无则[]"]
        }
    ],
    "estimated_total_words": 总字数估算,
    "story_arc": "一句话故事弧线（30字以内）"
}"""


async def planner_node(state: NovelState) -> dict:
    """Planner Agent Node - LLM驱动的任务规划

    根据意图和用户需求，智能分解为可执行的子任务。

    Args:
        state: 当前状态

    Returns:
        更新状态的部分字典，包含任务计划
    """
    user_request = state.get("user_request", "")
    genre = state.get("genre", "仙侠")
    intent = state.get("intent", "new_story")

    logger.info("planner.start", intent=intent, user_request=user_request)

    try:
        llm = get_llm(temperature=0.3)
        planning_prompt = f"""{PLANNER_SYSTEM_PROMPT}

用户需求：{user_request}
题材：{genre}
识别到的意图：{intent}

请根据以上信息，规划最优的任务执行顺序。
- 优先级：用户明确要求的先做
- 依赖关系：需要先建立基础的任务先做（如世界观→角色→情节→写作）
- 动态调整：根据题材特点调整任务颗粒度
"""
        response = await ainvoke_with_timeout(llm, planning_prompt, timeout=60)

        content = response["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        plan_data = json.loads(content.strip())

        logger.info("planner.complete",
            task_count=len(plan_data.get("tasks", [])),
            estimated_words=plan_data.get("estimated_total_words", 0)
        )

        return {
            "task_plan": plan_data.get("tasks", []),
            "total_chapters": plan_data.get("estimated_chapters", 3),
            "phase": "planning",
        }

    except Exception as e:
        logger.error("planner.failed", error=str(e))
        # 降级为简单任务计划
        fallback_tasks = [
            {
                "task_id": "task-1",
                "type": "world_building",
                "description": "构建世界观",
                "dependencies": [],
                "estimated_words": 500,
            },
            {
                "task_id": "task-2",
                "type": "chapter_write",
                "description": "创作第一章",
                "dependencies": ["task-1"],
                "estimated_words": 3000,
            },
        ]
        return {
            "task_plan": fallback_tasks,
            "total_chapters": 1,
            "phase": "planning",
        }


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
            "phase": "planning",
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

        # 注入风格约束
        style_constraints = _get_style_constraints(state)
        if style_constraints:
            prompt += style_constraints

        # 调用 LLM 生成正文
        response = await call_llm(prompt)
        draft = response.replace("---END---", "").strip()
        logger.info("scribe.complete", word_count=len(draft))

        # === 敏感词检测 ===
        from ai_agent.guardrail.sensitive_word_filter import check_sensitive_words

        check_result = check_sensitive_words(draft)
        if not check_result.is_clean:
            logger.warning(
                "scribe.sensitive_words_detected",
                found_words=check_result.found_words,
                confidence=check_result.confidence,
            )
            # 使用过滤后的文本
            draft = check_result.filtered_text

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
        current = state["current_chapter"]
        total = state.get("total_chapters", 1)

        # 保存当前章节到已完成列表
        completed_chapter = {
            "chapter": current,
            "title": state.get("outline", {}).get(f"ch_{current}_title", f"第{current}章"),
            "draft": draft,
            "word_count": len(draft),
        }

        if current < total:
            # 还有下一章
            next_chapter = current + 1
            return Command(
                update={
                    "draft": None,
                    "completed_chapters": [completed_chapter],
                    "current_chapter": next_chapter,
                    "phase": "writing",
                    "messages": [{"role": "assistant", "content": f"✅ 第{current}章已完成，开始第{next_chapter}章"}],
                    "interrupt_options": None,
                    "interrupt_value": None,
                },
                goto="scribe",
            )
        else:
            # 最后一章完成
            return Command(
                update={
                    "draft": draft,
                    "completed_chapters": [completed_chapter],
                    "phase": "complete",
                    "messages": [{"role": "assistant", "content": f"✅ 第{current}章已完成，全书创作完毕！"}],
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
                "total_chapters": 3,
                "completed_chapters": [],
                "phase": "idle",
                "messages": [{"role": "assistant", "content": "🔄 开始新创作..."}],
                "interrupt_options": None,
                "interrupt_value": None,
            },
            goto=END,
        )


# === Delegator Node (Subagent Task Delegation) ===

DELEGATOR_SYSTEM_PROMPT = """你是一个专业的任务协调助手。

当遇到以下情况时，使用 task 或 parallel_task 工具委派任务：
1. 任务需要并行处理以提高效率
2. 任务需要不同专业能力（研究/编码/审查）
3. 任务可以分解为多个独立子任务

可用的工具：
- task: 创建单个 Subagent 执行任务
- parallel_task: 并行创建多个 Subagent 同时执行任务

任务类型：
- research: 研究分析任务
- coding: 编程任务
- review: 审查任务
- general: 一般任务

返回格式（JSON）：
{
    "use_delegation": true/false,
    "delegation_type": "single/parallel/none",
    "tasks": [
        {
            "task_type": "任务类型",
            "description": "任务描述",
            "params": {},
            "config": {}
        }
    ]
}"""


async def delegator_node(state: NovelState) -> dict:
    """Delegator Agent Node - 任务委派

    决策是否需要将任务委派给 Subagent。

    Args:
        state: 当前状态

    Returns:
        更新状态的部分字典
    """
    logger.info("delegator.start")

    # 检查是否需要任务委派
    user_request = state.get("user_request", "")
    intent = state.get("intent")

    # 只有在特定意图下才考虑委派
    if intent not in ["new_story", "story_creation"]:
        return {"phase": state.get("phase", "idle")}

    try:
        llm = get_llm(temperature=0.3)
        full_prompt = f"""{DELEGATOR_SYSTEM_PROMPT}

当前状态：
- 用户请求：{user_request}
- 当前阶段：{state.get('phase')}

请判断是否需要使用 Subagent 委派任务。
"""
        response = await ainvoke_with_timeout(llm, full_prompt, timeout=30)

        # 解析响应
        content = response["content"]
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            delegation_data = json.loads(content.strip())
        except json.JSONDecodeError:
            delegation_data = {"use_delegation": False}

        # 执行委派任务
        if delegation_data.get("use_delegation", False):
            delegation_type = delegation_data.get("delegation_type", "none")
            tasks = delegation_data.get("tasks", [])

            if not tasks:
                return {"phase": state.get("phase", "idle")}

            if delegation_type == "parallel" and len(tasks) > 1:
                # 并行执行
                logger.info("delegator.parallel", task_count=len(tasks))
                result_json = await parallel_task_tool(tasks=tasks)
                result_data = json.loads(result_json)

                return {
                    "delegation_result": result_data,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": f"📋 并行任务完成：{result_data.get('summary_report', '')}",
                        }
                    ],
                }
            elif delegation_type == "single" and tasks:
                # 单个任务
                task = tasks[0]
                logger.info("delegator.single", task_type=task.get("task_type"))
                result_json = await task_tool(
                    task_type=task.get("task_type", "general"),
                    description=task.get("description", ""),
                    params=task.get("params", {}),
                )
                result_data = json.loads(result_json)

                return {
                    "delegation_result": result_data,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": f"📋 任务完成：{result_data.get('summary', '')}",
                        }
                    ],
                }

    except Exception as e:
        logger.error("delegator.failed", error=str(e))

    return {"phase": state.get("phase", "idle")}


def _router(state: NovelState) -> Literal["intent", "planner", "narrator", "scribe", "delegator", "__end__"]:
    """LLM驱动的路由函数 — 根据当前状态和意图决定下一步

    智能流程：
    - idle → intent（识别用户意图）
    - intent → planner（new_story时进入规划）
    - planner → narrator/world_builder（根据任务计划）
    - narrator → scribe（生成章节）
    - scribe → 循环直到任务完成
    - phase == complete → __end__
    """
    phase = state.get("phase", "idle")
    intent = state.get("intent")
    task_plan = state.get("task_plan")
    outline = state.get("outline")

    # 阶段1：意图识别
    if phase == "idle" and not intent:
        return "intent"

    # 阶段2：任务规划（仅对新故事）
    if intent == "new_story" and not task_plan:
        return "planner"

    # 阶段3：执行任务计划
    if task_plan and not outline:
        # 检查第一个未完成的任务类型
        current_task = None
        for task in task_plan:
            if task.get("status") != "completed":
                current_task = task
                break

        if current_task:
            task_type = current_task.get("type", "")
            if task_type == "world_building":
                return "narrator"  # narrator负责世界观构建
            elif task_type == "chapter_write":
                return "scribe"
            else:
                return "narrator"  # 默认走narrator
        else:
            # 所有任务完成
            return "__end__"

    # 阶段4：多章节流程
    if outline and state.get("draft") is None and phase in ("planning", "writing"):
        return "scribe"

    # 阶段5：任务委派（可选）
    # 如果有 delegation_result 但还没有进入正常流程，可以进入 delegator
    if state.get("intent") == "new_story" and state.get("task_plan") and not state.get("outline"):
        # 检查 delegation_result 是否存在
        if state.get("delegation_result"):
            return "delegator"

    # 完成
    if phase == "complete":
        return "__end__"

    # 其他情况结束
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

    # 添加所有节点
    builder.add_node("intent", intent_node)
    builder.add_node("planner", planner_node)
    builder.add_node("narrator", narrator_node)
    builder.add_node("scribe", scribe_node)
    builder.add_node("delegator", delegator_node)

    # START → 条件路由
    builder.add_conditional_edges(
        START,
        _router,
        {
            "intent": "intent",
            "planner": "planner",
            "narrator": "narrator",
            "scribe": "scribe",
            "delegator": "delegator",
            "__end__": END,
        },
    )

    # 所有节点执行完后回到路由器重新判断
    for node in ["intent", "planner", "narrator", "scribe", "delegator"]:
        builder.add_conditional_edges(
            node,
            _router,
            {
                "intent": "intent",
                "planner": "planner",
                "narrator": "narrator",
                "scribe": "scribe",
                "delegator": "delegator",
                "__end__": END,
            },
        )

    # 编译
    graph = builder.compile(checkpointer=checkpointer, store=store)

    # 判断 checkpointer 类型
    checkpointer_name = "RedisSaver"
    try:
        from langgraph.checkpoint.redis import RedisSaver
        if not isinstance(checkpointer, RedisSaver):
            checkpointer_name = "MemorySaver"
    except Exception:
        checkpointer_name = "MemorySaver"
    logger.info("novel_graph.built", checkpointer=checkpointer_name)
    return graph


# === Global Graph Instance ===
novel_graph = build_novel_graph()
