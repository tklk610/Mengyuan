# Harness Engineering - NovelCraft PoC

> AI Agent 工程化框架演示项目：小说创作多智能体系统

## 项目状态

| 版本 | 状态 | 说明 |
|------|------|------|
| v1.1.0 | ✅ 完成 | 文件操作沙箱机制（七层防护 + 容器级沙箱） |
| v0.5.0 | ✅ 完成 | DeepAgent 架构改造 |
| v0.4.0 | ✅ 完成 | Phase 3: 多章节创作/导出/会话管理 |
| v0.3.0 | ✅ 完成 | Phase 2: 风格学习与记忆 |
| v0.2.0 | ✅ 完成 | NovelCraft PoC Phase 1 MVP |

## 核心功能

- **多智能体协作** - Narrator Agent（大纲规划）+ Scribe Agent（正文续写）+ Stylist Agent（风格控制）
- **HITL 中断机制** - 人工审阅草稿，决定接受/重写/重启
- **风格学习** - 上传小说样本，自动提取风格特征并注入创作约束
- **多章节创作** - 支持创作多章节小说，自动章节递增
- **导出功能** - 支持 txt 格式导出完整小说
- **会话管理** - 历史会话持久化与恢复
- **Subagent 任务委派** - 主 Agent 可委派任务给专业 Subagent（并行/串行）
- **DeepAgent 架构** - 基于 `create_deep_agent()` 的现代化 Agent 架构

## 技术栈

| 组件 | 技术 |
|------|------|
| Agent 框架 | LangGraph 1.x + DeepAgent 0.7.7 |
| Web 框架 | FastAPI |
| 向量数据库 | Qdrant |
| 关系数据库 | PostgreSQL |
| 缓存 | Redis |
| 部署 | Docker Compose |

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd Harness_Engineering

# 2. 安装依赖
pip install -e .

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 4. 启动服务
docker-compose up -d

# 5. 访问 API 文档
open http://localhost:8000/docs
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/session` | POST | 创建创作会话 |
| `/api/chat` | POST | SSE 聊天/创作 |
| `/api/resume` | POST | 恢复中断任务 |
| `/api/styles` | GET/POST | 风格档案管理 |
| `/api/styles/search` | POST | 相似风格搜索 |
| `/api/preferences` | GET/PUT | 用户偏好管理 |
| `/api/export` | POST | 导出 txt 文件 |
| `/api/outline` | PUT | 大纲编辑 |
| `/api/sessions` | GET | 列出历史会话 |
| `/api/sessions/{thread_id}` | GET | 获取会话详情 |

## DeepAgent 架构

项目支持两种 Agent 架构：

### 原始架构（LangGraph）
- 文件：`src/ai_agent/agents/novel_agent.py`
- 使用 LangGraph StateGraph 定义流程
- 节点：intent → planner → narrator → scribe → delegator

### DeepAgent 架构（新）
- 文件：`src/ai_agent/agents/deep_novel_agent.py`
- 使用 `create_deep_agent()` 创建
- 自动内置 Middleware：

| Middleware | 工具 | 功能 |
|------------|------|------|
| TodoListMiddleware | `write_todos` | 任务规划追踪 |
| FilesystemMiddleware | `ls/read_file/write_file` | 文件操作 |
| SubAgentMiddleware | `task` | 任务委派 |
| HumanInTheLoopMiddleware | `interrupt_on` | 人工审批 |
| SkillsMiddleware | 自动加载 | Skill 加载 |
| MemoryMiddleware | `store` | 跨会话记忆 |

### 内置 Subagents

| Subagent | 职责 | 工具 |
|----------|------|------|
| `narrator` | 大纲规划 | `plan_outline` |
| `scribe` | 章节写作 | `write_chapter` |
| `stylist` | 风格分析 | `analyze_style` |

## 沙箱机制

项目实现了**两层沙箱**，提供七层防护架构：

### 七层应用层沙箱（Python）

| 层级 | 组件 | 功能 |
|------|------|------|
| Layer 1 | PathGuard | 路径遍历防护（`../` 逃逸检测）、系统敏感路径保护 |
| Layer 2 | ContentGuard | 恶意代码/注入攻击/敏感信息检测 |
| Layer 3 | PolicyGuard | 白名单/黑名单操作控制、配额限制 |
| Layer 4 | VirtualFileSystem | 虚拟文件系统，内存操作不实际访问磁盘 |
| Layer 5 | SkillSandboxLoader | Skill 安全加载、frontmatter 验证 |
| Layer 6 | SandboxMiddleware | 危险操作拦截、HITL 人工审批 |
| Layer 7 | SandboxPool | 用户级沙箱隔离、池管理、LRU 驱逐、预热机制 |

### 用户隔离与池管理

```python
from ai_agent.sandbox import SandboxPool, FileSandbox

# 用户级沙箱隔离
pool = SandboxPool(max_size=10, idle_timeout=300)

async with pool.get_sandbox("user_123") as sandbox:
    await sandbox.write("novel_chapter1.txt", novel_content)
    # 每个用户独立沙箱实例，root_dir = ./workspace/user_123
```

### 容器层沙箱（Docker）

| 安全措施 | 配置 |
|----------|------|
| 只读文件系统 | `read_only: true` |
| 禁止提权 | `no-new-privileges: true` |
| 非 root 用户 | `user: "1000:1000"` |
| 资源限制 | 0.5 CPU / 512MB 内存 / 100 进程 |
| tmpfs 挂载 | `/tmp:size=50M,noexec,nosuid,nodev` |
| 只读卷挂载 | `./src:/workspace/src:ro` |

```bash
# 启动沙箱容器
docker-compose -f docker-compose.sandbox.yml up agent-sandboxed -d

# 或在沙箱中运行命令
docker run --rm \
  --security-opt no-new-privileges:true \
  --read-only \
  --user 1000:1000 \
  -v $(pwd)/src:/workspace:ro \
  novelcraft-sandbox \
  pytest tests/unit/ -v
```

详细配置见 [docs/SANDBOX.md](docs/SANDBOX.md)

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 单元测试
pytest tests/unit/ -v

# DeepAgent 架构测试
pytest tests/unit/agents/test_deep_novel_agent.py -v

# Phase 3 集成测试
pytest tests/integration/api/test_phase3_features.py -v
```

## 项目结构

```
Harness_Engineering/
├── src/ai_agent/              # 业务代码
│   ├── agents/                # Agent 实现
│   │   ├── novel_agent.py     #    原始 LangGraph Agent
│   │   ├── deep_novel_agent.py #    DeepAgent 架构 (新)
│   │   ├── subagent.py        #    Subagent 执行器
│   │   ├── stylist_agent.py   #    风格分析 Agent
│   │   └── state.py           #    LangGraph State
│   ├── api/                   # FastAPI 端点
│   ├── auth/                  # 认证 (JWT)
│   ├── config/                # 配置 (Pydantic Settings)
│   ├── exporters/             # 导出模块 (txt)
│   ├── guardrail/             # 安全 Guardrail
│   │   └── sensitive_word_filter.py # 敏感词检测
│   ├── llm/                   # LLM 工厂
│   ├── rag/                   # RAG 组件
│   │   ├── qdrant_client.py   #    Qdrant 向量存储
│   │   ├── embeddings.py      #    Embedding 生成
│   │   └── style_analyzer.py  #    风格分析
│   ├── schemas/               # Pydantic DTO
│   │   ├── chat.py            #    Chat 请求/响应
│   │   └── task.py            #    Task 任务模型
│   └── tools/                 # 工具
│       └── subagent_task.py   #    Subagent Task Tool
├── tests/                     # 测试
│   ├── unit/                  #    单元测试 (91 passed)
│   └── integration/           #    集成测试
├── skills/                    # DeepAgent Skills
│   └── novel-craft/           #    NovelCraft Skill
│       └── SKILL.md           #    Skill 定义
├── .harness/                  # Harness 约束
│   ├── agents/                #    Agent 模板
│   ├── changes/               #    变更记录
│   ├── rules/                 #    工程规范
│   ├── skills/                #    Skill 定义
│   └── wiki/                  #    架构文档
├── docs/                      # 项目文档
└── scripts/                   # 工具脚本
```

## 约束与规范

本项目遵循 **Harness Engineering** 约束：

- `.claude/Claude.md` - AI 编码全局红线（R1-R16）
- `.harness/rules/` - 工程规范 / 编码规范 / 开发流程 / AI 特殊红线

## Changelog

详见 [CHANGELOG.md](CHANGELOG.md)
