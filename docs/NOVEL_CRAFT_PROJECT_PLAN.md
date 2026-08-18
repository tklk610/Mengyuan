# NovelCraft 小说创作多智能体系统 - 项目设计开发方案

## 一、系统概述

### 1.1 项目定位
NovelCraft 是一个面向严肃创作者的小说 AI 助手，基于 Deep Agents 框架构建的多智能体协作平台。系统模仿专业写作流程，支持从零创作小说、根据片段续写、学习风格特征等核心功能。

### 1.2 技术选型依据
根据 `framework-selection` skill 的决策指南，本项目特性符合使用 **Deep Agents** 的条件：
- ✅ 多步骤任务（创作、续写、风格学习）
- ✅ 需要文件管理和持久化记忆
- ✅ 需要子 Agent 委托专业任务
- ✅ 需要 Human-in-the-loop 人工介入

### 1.3 技术栈总览
| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 前端 | Next.js 14 (App Router) | Web 聊天界面 + 创作工作台 |
| 后端 | FastAPI | API 网关 + 异步任务 |
| Agent 框架 | LangGraph 1.x | 多智能体编排引擎（原生 LangGraph，无额外框架依赖）|
| 向量存储 | Qdrant | 风格样本向量检索（轻量级） |
| 关系数据库 | PostgreSQL | 用户、项目、偏好存储 |
| 缓存 | Redis | 会话缓存、任务队列 |
| 搜索 | Tavily MCP / DuckDuckGo | 事实核查联网搜索 |
| 部署 | Docker Compose | 本地+云端通用 |

---

## 二、总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    展示层 (Presentation Layer)               │
│  Next.js 14 + TailwindCSS + Zustand                         │
│  - 聊天界面 / 创作工作台 / 大纲可视化 / 风格卡片 / 导出      │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP + SSE
┌────────────────────────────▼────────────────────────────────┐
│                    API 网关层 (API Gateway)                  │
│  FastAPI + Uvicorn                                           │
│  - /session, /chat, /upload, /export, /memory 等端点        │
│  - JWT 认证 / 请求日志 / 限流 / CORS                         │
│  - Celery + Redis 异步任务队列                               │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                 Deep Agents 编排层                           │
│  create_deep_agent() - 多 Agent 协作中枢                    │
│  - TodoListMiddleware: 任务规划与追踪                        │
│  - SubAgentMiddleware: 子 Agent 委托                         │
│  - HumanInTheLoopMiddleware: 人工审批中断                    │
│  - SkillsMiddleware: 按需加载专业技能                        │
│  - MemoryMiddleware: 跨会话持久化记忆                        │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                      Agent 层 (Multi-Agent)                  │
│  ┌──────────────┬──────────────┬──────────────┐              │
│  │ Narrator     │ Stylist      │ Scribe       │              │
│  │ (剧情规划)   │ (风格控制)   │ (续写执行)   │              │
│  ├──────────────┼──────────────┼──────────────┤              │
│  │ FactChecker  │ Polisher     │ Editor       │              │
│  │ (事实核查)   │ (润色校对)   │ (评估选择)   │              │
│  └──────────────┴──────────────┴──────────────┘              │
│  每个 Agent = Deep Agent Node + LLM + Tools + Prompt         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    工具与技能层 (Tools & Skills)              │
│  - MCP Server: 联网搜索 (Tavily/DuckDuckGo)                  │
│  - 内部工具: 文本分割 / 情感分析 / 大纲差异比较              │
│  - Skills: novel-writing / style-analysis / fact-check       │
│  - RAG: Qdrant 向量检索 + 上下文增强                         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    记忆与存储层 (Memory & Storage)            │
│  - 长期记忆: PostgreSQL + Qdrant (用户偏好 / 风格档案)       │
│  - 会话状态: Redis + LangGraph Checkpoint                    │
│  - 知识库: Qdrant 向量库 (小说样本 / 风格特征)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、数据模型设计

### 3.1 核心实体关系
```
User (用户)
├── id: UUID (PK)
├── username: VARCHAR
├── email: VARCHAR
├── password_hash: VARCHAR
├── created_at: TIMESTAMP
└── preferences: JSONB (偏好设置)

Project (项目)
├── id: UUID (PK)
├── user_id: UUID (FK → User)
├── title: VARCHAR
├── genre: VARCHAR (仙侠/修仙/奇幻/悬疑/言情/科幻)
├── outline: JSONB (大纲结构)
├── style_profile_id: UUID (FK → StyleProfile, 可空)
├── status: VARCHAR (创作中/已完成/已归档)
├── created_at: TIMESTAMP
└── updated_at: TIMESTAMP

Chapter (章节)
├── id: UUID (PK)
├── project_id: UUID (FK → Project)
├── chapter_number: INT
├── title: VARCHAR
├── content: TEXT
├── status: VARCHAR (草稿/润色/定稿)
├── word_count: INT
├── created_at: TIMESTAMP
└── updated_at: TIMESTAMP

StyleProfile (风格档案)
├── id: UUID (PK)
├── user_id: UUID (FK → User)
├── name: VARCHAR
├── genre_tags: VARCHAR[]
├── characteristics: JSONB
│   ├── sentence_structure: STRING
│   ├── description_density: FLOAT
│   ├── dialogue_style: STRING
│   ├── pacing: STRING
│   └── banned_words: STRING[]
├── embedding: ARRAY[FLOAT] (用于向量检索)
├── sample_source: VARCHAR (来源作品名)
└── created_at: TIMESTAMP

NovelSample (小说样本)
├── id: UUID (PK)
├── user_id: UUID (FK → User)
├── title: VARCHAR
├── author: VARCHAR
├── content: TEXT
├── chunks: JSONB (分块后的段落)
├── style_profile_id: UUID (FK → StyleProfile)
└── uploaded_at: TIMESTAMP

UserPreference (用户偏好)
├── id: UUID (PK)
├── user_id: UUID (FK → User, 唯一)
├── narrative_pov: VARCHAR (第一人称/第三人称/全知视角)
├── target_word_count: INT (每章目标字数)
├── ending_preference: VARCHAR (HE/BE/NE/开放)
├── pacing_preference: VARCHAR (快节奏/中等/慢热)
├── avoid_elements: VARCHAR[] (避免的元素)
├── preferred_tones: VARCHAR[] (冷峻/轻松/史诗/日常)
└── updated_at: TIMESTAMP

Foreshadowing (伏笔记录)
├── id: UUID (PK)
├── project_id: UUID (FK → Project)
├── description: TEXT
├── planted_chapter: INT
├── expected_reveal_chapter: INT
├── status: VARCHAR (埋伏/揭示/遗忘)
└── created_at: TIMESTAMP
```

### 3.2 LangGraph State Schema
```python
class NovelState(TypedDict):
    # 用户输入
    messages: Annotated[List[BaseMessage], operator.add]
    
    # 项目基础
    project_id: str
    user_id: str
    genre: str
    style_profile_id: Optional[str]
    
    # 创作内容
    outline: dict  # 结构化大纲
    characters: dict  # 角色档案
    context_window: str  # 最近N章滚动窗口
    current_chapter: int
    chapter_drafts: Annotated[List[dict], operator.add]
    
    # 记忆相关
    user_preferences: dict
    foreshadowing_tracker: Annotated[List[dict], operator.add]
    
    # 控制信号
    next_agent: str
    interrupt_message: Optional[str]
    user_choice: Optional[str]
    needs_fact_check: bool
    task_type: str  # "create" / "continue" / "style_learn"
```

---

## 四、多 Agent 详细设计

### 4.1 Agent 职责定义

#### 4.1.1 Narrator (剧情规划 Agent)
```
职责: 从零创作时生成大纲和人设
触发: 用户选择"新小说创作"且无现成大纲
输入: 用户需求描述、体裁、风格指南摘要
输出: 结构化大纲 + 角色档案
工具: write_todos (任务规划)
子Agent: 无
```

#### 4.1.2 Stylist (风格控制 Agent)
```
职责: 管理风格约束，将用户偏好转化为 prompt 指导
触发: 用户上传风格样本 / 选择已有风格档案
输入: 风格样本 / 风格档案ID / 用户偏好
输出: 风格约束字典 (sentence_structure, banned_words 等)
工具: RAG 检索 (Qdrant)
子Agent: 无
```

#### 4.1.3 Scribe (续写执行 Agent)
```
职责: 核心写作执行，生成小说正文
触发: 章节创作请求
输入: 大纲节点、角色状态、上下文窗口、风格约束
输出: 章节草稿
工具: RAG (Few-shot 示例)
子Agent: 无
```

#### 4.1.4 FactChecker (事实核查 Agent)
```
职责: 检测文本中的事实性陈述并联网校验
触发: 自动检测到可验证断言 (地名/日期/科学数据)
输入: 待核查文本片段
输出: 核查报告 + 修正建议
工具: web_search (Tavily/DuckDuckGo MCP)
子Agent: 无
```

#### 4.1.5 Polisher (润色校对 Agent)
```
职责: 基础校对、流畅度优化、情感基调微调
触发: 章节定稿前 / 用户手动请求
输入: 原始文本 + 润色级别 + 情感目标
输出: 润色后文本
工具: 无 (纯 LLM)
子Agent: 无
```

#### 4.1.6 Editor (评估选择 Agent)
```
职责: 多分支评估、用户选择引导
触发: Scribe 生成多个版本 / 用户请求分支选择
输入: 多个版本草稿 + 评估维度
输出: 排名列表 + 推荐
工具: 无 (纯 LLM)
子Agent: 无
```

### 4.2 子 Agent 注册 (Deep Agents)
```python
subagents=[
    {
        "name": "narrator",
        "description": "剧情规划 - 生成小说大纲和角色设定",
        "system_prompt": "你是一位专业的小说剧情规划师...",
        "tools": [search_background_knowledge],
    },
    {
        "name": "stylist", 
        "description": "风格控制 - 分析和匹配写作风格",
        "system_prompt": "你是一位文学风格分析师...",
        "tools": [retrieve_style_profile, analyze_style],
    },
    {
        "name": "scribe",
        "description": "续写执行 - 创作小说正文",
        "system_prompt": "你是一位专业小说作家...",
        "tools": [retrieve_style_examples, get_context],
    },
    {
        "name": "fact_checker",
        "description": "事实核查 - 联网校验事实性内容",
        "system_prompt": "你是一位严谨的事实核查员...",
        "tools": [web_search, Tavily_search],
    },
    {
        "name": "polisher",
        "description": "润色校对 - 优化文字质量和表达",
        "system_prompt": "你是一位资深文字编辑...",
        "tools": [],
    },
    {
        "name": "editor",
        "description": "评估选择 - 评估和推荐最佳版本",
        "system_prompt": "你是一位资深文学编辑...",
        "tools": [],
    },
]
```

---

## 五、核心流程设计

### 5.1 从零创作新小说流程
```
用户输入需求 
    ↓
Narrator 生成大纲 + 角色设定
    ↓
Stylist 加载风格约束 (如有风格样本则分析学习)
    ↓
Scribe 生成第一章
    ↓
[如需事实核查] → FactChecker
    ↓
用户中断确认 (interrupt) → 接受/修改/重写/分支
    ↓
Polisher 润色
    ↓
Editor 多分支评估 (如有)
    ↓
保存章节 → 下一章循环
```

### 5.2 续写现有章节流程
```
用户选择项目 + 输入续写要求
    ↓
加载项目上下文 (大纲 + 最近3章内容)
    ↓
Stylist 应用项目风格约束
    ↓
Scribe 生成续写内容
    ↓
用户中断确认
    ↓
Polisher 润色 → 保存
```

### 5.3 风格学习流程
```
用户上传小说样本 (txt/epub)
    ↓
预处理: 解析 + 清洗 + 分块
    ↓
Stylist 分析风格特征
    ↓
生成风格档案 (存入 PostgreSQL + Qdrant)
    ↓
返回风格卡片给用户确认
```

---

## 六、Skills 设计

### 6.1 目录结构
```
skills/
├── novel-writing/
│   ├── SKILL.md        # 小说创作技能
│   └── prompts.py      # 创作模板
├── style-analysis/
│   ├── SKILL.md        # 风格分析技能
│   └── analysis.py     # 分析工具
├── fact-check/
│   ├── SKILL.md        # 事实核查技能
│   └── checkers.py     # 核查规则
└── project-management/
    ├── SKILL.md        # 项目管理技能
    └── templates/      # 大纲模板
```

### 6.2 SKILL.md 示例 (novel-writing)
```markdown
---
name: novel-writing
description: "INVOKE THIS SKILL when创作小说正文、续写章节、生成对话。 Covers plot development, character voice, pacing, and genre-specific techniques."
---

# Novel Writing Skill

## Overview
专业小说创作技能，支持多种题材（仙侠、修仙、奇幻、悬疑等）的正文生成。

## When to Use
- 用户要求创作新小说或续写章节
- 需要生成对话、描写、场景转换
- 需要保持角色一致性

## Instructions
### 仙侠/修仙类创作规范
1. 世界观: 境界设定 (炼气→筑基→金丹→元婴→化神...)
2. 法宝丹药: 遵循等级体系
3. 文风: 古风典雅，善用成语典故
4. 节奏: 修炼突破循环 (压抑→爆发)

### 续写规范
1. 保持上下文连贯
2. 角色语言风格一致
3. 控制每章 2000-4000 字
4. 章末设置悬念或钩子
```

---

## 七、API 设计

### 7.1 端点总览
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /auth/register | 用户注册 |
| POST | /auth/login | 用户登录 |
| POST | /session | 创建创作会话 |
| GET | /session/{session_id} | 获取会话状态 |
| POST | /chat/{session_id} | 发送消息 (SSE 流) |
| POST | /upload/sample | 上传风格样本 |
| GET | /styles | 列出风格档案 |
| PUT | /memory/preferences | 更新用户偏好 |
| GET | /project/{project_id} | 获取项目详情 |
| POST | /project | 创建新项目 |
| PUT | /project/{project_id}/outline | 更新大纲 |
| GET | /chapter/{chapter_id} | 获取章节内容 |
| POST | /export/{project_id} | 请求导出 |

### 7.2 SSE 事件流
```typescript
// 事件类型
type SSEEvent = 
  | { type: "agent_update"; agent: string; status: string; message: string }
  | { type: "content_delta"; text: string }
  | { type: "interrupt"; options: string[]; draft: string }
  | { type: "task_complete"; chapter_id: string }
  | { type: "error"; message: string }
```

---

## 八、前端设计

### 8.1 页面结构
```
/app
├── /page.tsx                    # 首页/登录
├── /dashboard/page.tsx          # 项目列表
├── /project/[id]/page.tsx       # 创作界面
│   ├── /chat                     # 聊天模式
│   ├── /outline                  # 大纲编辑
│   ├── /characters               # 角色管理
│   ├── /styles                   # 风格管理
│   └── /export                   # 导出设置
└── /settings/page.tsx           # 用户设置
```

### 8.2 核心组件
```typescript
// 状态管理 (Zustand)
interface AppState {
  // 会话
  currentSession: Session | null
  messages: Message[]
  
  // 项目
  currentProject: Project | null
  outline: Outline | null
  chapters: Chapter[]
  
  // 创作
  currentDraft: string
  isGenerating: boolean
  pendingInterrupt: Interrupt | null
  
  // 动作
  sendMessage: (content: string) => void
  acceptDraft: () => void
  requestRewrite: (instruction: string) => void
  createBranch: () => void
}
```

---

## 九、部署架构

### 9.1 Docker Compose 配置
```yaml
services:
  # 前端
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000

  # 后端 API
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/novelcraft
      - REDIS_URL=redis://cache:6379
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - db
      - cache
      - qdrant

  # 数据库
  db:
    image: postgres:16
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=novelcraft
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # 缓存
  cache:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # 向量数据库
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage

  # 异步任务
  celery:
    build: ./backend
    command: celery -A app.celery worker
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/novelcraft
      - REDIS_URL=redis://cache:6379
    depends_on:
      - db
      - cache

volumes:
  pgdata:
  qdrant_storage:
```

---

## 十、开发路线图

### Phase 1: MVP (2-3 周)
**目标**: 基础创作流程跑通

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第1周 | 1. 项目初始化 (Next.js + FastAPI)<br>2. Docker Compose 环境搭建<br>3. 数据库模型设计<br>4. 基础 Auth (JWT) | 可运行的空项目，数据库连接正常 |
| 第2周 | 1. Deep Agents 核心配置<br>2. Narrator + Scribe Agent 实现<br>3. 基础聊天 UI<br>4. 创作流程串联 | 能输入梗概生成一段小说 |
| 第3周 | 1. Human-in-the-loop 中断机制<br>2. 章节保存与加载<br>3. 基础样式和响应式布局<br>4. 初步测试 | 完整的创作-确认流程 |

### Phase 2: 风格学习与记忆 (3-4 周)
**目标**: 风格样本上传分析 + 用户偏好记忆

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第4周 | 1. 风格样本上传与解析<br>2. Qdrant 向量数据库集成<br>3. Stylist 风格分析实现 | 风格档案生成 |
| 第5周 | 1. RAG 检索增强<br>2. Scribe 风格约束注入<br>3. 风格卡片展示 UI | 风格匹配创作 |
| 第6周 | 1. 用户偏好模型<br>2. MemoryMiddleware 配置<br>3. 偏好记忆持久化<br>4. 偏好设置页面 | 偏好记忆功能 |

### Phase 3: 高级功能 (2-3 周)
**目标**: 事实核查 + 多分支 + 导出

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第7周 | 1. FactChecker Agent + MCP 搜索<br>2. 事实核查 UI 提示<br>3. 可配置核查开关 | 事实核查功能 |
| 第8周 | 1. 多分支生成逻辑<br>2. Editor Agent 评估<br>3. 分支选择 UI<br>4. 分支管理 | 多分支剧情 |
| 第9周 | 1. 导出服务 (Celery)<br>2. txt/epub/pdf 生成器<br>3. 导出预览 UI<br>4. 下载链接生成 | 导出功能 |

### Phase 4: 优化与交付 (2 周)
**目标**: 性能优化 + 完善文档

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第10周 | 1. 流式输出优化<br>2. 缓存策略优化<br>3. 并发处理优化<br>4. 错误处理完善 | 性能优化 |
| 第11周 | 1. 完整 API 文档<br>2. 部署文档<br>3. 用户手册<br>4. 演示视频 | 交付文档 |

---

## 十一、环境变量配置

```env
# .env 示例
# Database
DATABASE_URL=postgresql://novelcraft:password@localhost:5432/novelcraft

# Redis
REDIS_URL=redis://localhost:6379

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=novelcraft_styles

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MINMAX_API_KEY=your-minmax-key

# Auth
JWT_SECRET=your-super-secret-jwt-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Tavily (可选)
TAVILY_API_KEY=tvly-...

# Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
```

---

## 十二、关键技术要点 (基于 Skills)

### 12.1 LangGraph 配置（原生，无 deepagents）

本项目使用原生 LangGraph 1.x，不引入 deepagents 框架，以避免两套 Skills 体系冲突和额外依赖风险。

```python
from langgraph.checkpoint.redis import RedisSaver   # 生产用（Redis 跨进程共享 session）
from langgraph.checkpoint.memory import MemorySaver  # 开发用（无外部依赖）
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, interrupt

# === Agent Node 函数 ===
async def narrator_node(state: NovelState) -> dict:
    """Narrator: 生成故事大纲（三幕结构 + 角色设定）"""
    outline = await generate_outline(state)
    return {
        "outline": outline,
        "characters": outline.get("characters", {}),
        "phase": "planning_complete",
    }

async def scribe_node(state: NovelState) -> Command:
    """Scribe: 生成正文 + HITL 中断

    interrupt() 首次调用时抛出 GraphInterrupt，结果含 __interrupt__；
    /api/resume 传入 Command(resume={...}) 后，interrupt() 返回该字典，
    scribe_node 提取 user_choice = choice.get("choice") 做路由判断。
    """
    draft = await generate_chapter(state)

    # 中断等待用户确认
    interrupt_value = {
        "draft": draft,
        "options": ["accept", "rewrite", "restart"],
        "message": "请审阅本章草稿",
        "was_interrupted": True,
    }
    state["interrupt_value"] = interrupt_value
    choice = interrupt(interrupt_value)  # 首次抛出 GraphInterrupt

    # 重入时 interrupt() 返回 Command(resume={...}) 的字典
    user_choice = choice.get("choice") if isinstance(choice, dict) else choice

    if user_choice == "accept":
        return Command(
            update={"draft": draft, "phase": "complete", "interrupt_value": None},
            goto=END,
        )
    elif user_choice == "rewrite":
        return Command(
            update={"phase": "writing", "interrupt_value": None},
            goto="scribe",
        )
    else:  # restart
        return Command(
            update={"phase": "idle", "outline": None, "draft": None},
            goto=END,
        )

# === 条件路由 ===
def _router(state: NovelState) -> str:
    if not state.get("outline"):
        return "narrator"
    if not state.get("draft"):
        return "scribe"
    return END

# === 构建 Graph ===
checkpointer = RedisSaver(redis_url=settings.redis_url)  # 生产
store = InMemoryStore()

builder = StateGraph(NovelState)
builder.add_node("narrator", narrator_node)
builder.add_node("scribe", scribe_node)
builder.add_edge(START, "narrator")
builder.add_conditional_edges("narrator", _router, {"narrator": "narrator", "scribe": "scribe", END: END})
builder.add_edge("scribe", END)

graph = builder.compile(checkpointer=checkpointer, store=store)
```

### 12.2 Human-in-the-loop 中断
```python
from langgraph.types import interrupt, Command

def scribe_node(state: NovelState) -> Command:
    draft = generate_chapter(state)

    # 中断等待用户确认（首次抛出 GraphInterrupt）
    choice = interrupt({
        "draft": draft,
        "options": ["accept", "rewrite", "branch"],
        "message": "请审阅本章草稿"
    })

    # interrupt() 返回 Command(resume={...}) 的完整字典，
    # user_choice 才是用户选择的字符串
    user_choice = choice.get("choice") if isinstance(choice, dict) else choice

    if user_choice == "accept":
        return Command(update={"draft": draft}, goto="polisher")
    elif user_choice == "rewrite":
        return Command(update={"rewrite_instruction": choice.get("instruction")}, goto="scribe")
    else:
        return Command(update={}, goto="editor")
```

### 12.3 多 Agent 协作（跨 Node 委托）
```python
# 在原生 LangGraph 中，跨 Agent 协作通过条件路由实现，
# 不需要 deepagents 的 task() 工具。
# 各 Agent 是同一个 graph 中的不同 node，共享 NovelState。

def _router(state: NovelState) -> str:
    """根据 phase 和 needs_fact_check 调度 Agent"""
    if state.get("needs_fact_check"):
        return "fact_checker"
    elif state.get("phase") == "polishing":
        return "polisher"
    elif state.get("phase") == "evaluating":
        return "editor"
    return END

# 各 Agent node 直接读写 state，无需序列化/反序列化
async def narrator_node(state: NovelState) -> dict:
    outline = await call_llm(prompt=f"生成{state['genre']}小说大纲...")
    return {"outline": outline, "phase": "writing"}

async def fact_checker_node(state: NovelState) -> dict:
    issues = await web_search(state.get("pending_facts", []))
    return {"needs_fact_check": False, "fact_issues": issues}
```
```

---

## 十三、注意事项

### 13.1 关于多 Agent 编排（原生 LangGraph）
- 各 Agent = 同一 graph 中的不同 node，共享 NovelState，无需 deepagents
- 跨 Agent 委托通过 `Command(goto="node_name")` 实现，不需要 task() 工具
- Agent 间共享 memory，通过 `store=InMemoryStore()` 或 `RedisStore`
- 无 deepagents 依赖，无额外框架学习成本

### 13.2 关于 LangGraph 的边界
- ✅ Node 必须返回部分更新 (dict)，不能返回完整 state
- ✅ List 字段需要 Reducer，否则会被覆盖
- ✅ Command 可以同时更新状态和路由
- ✅ `interrupt()` 首次调用抛出 GraphInterrupt；重入时返回 resume 字典

### 13.3 关于 Memory 与 Checkpointer
- ✅ Checkpointer: 单会话内持久化（HITL 依赖项）
- ✅ `MemorySaver`：开发用，无外部依赖
- ✅ `RedisSaver`：生产用，跨进程共享 session
- ⚠️ 必须配置 checkpointer 才能使用 interrupt

### 13.4 关于 Interrupt
- ⚠️ Interrupt 前代码会重复执行，需保证幂等性
- ⚠️ 必须配置 checkpointer 才能使用 interrupt
- ⚠️ `interrupt()` 首次抛出 GraphInterrupt；重入时返回 `Command(resume={...})` 的完整字典，
  node 内必须用 `choice.get("choice")` 提取字符串值再做路由判断

---

## 十四、后续扩展方向

1. **多语言支持**: 扩展到英文、日文等小说创作
2. **协作功能**: 多用户共同创作同一项目
3. **版本控制**: 章节历史版本管理与回滚
4. **语音输入**: 语音转文字创作方式
5. **社区分享**: 风格档案市场、模板分享
6. **深度定制**: 微调专属写作风格的模型
