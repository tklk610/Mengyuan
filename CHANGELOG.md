# Changelog

> 所有项目变更都会记录在此文件。
> 本文档遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/) 规范。
> 版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [1.1.0] - 2026-08-21

### Added（新增）

- **文件操作沙箱机制** —— 七层防护架构
  - `src/ai_agent/sandbox/` —— 沙箱模块完整实现
  - `src/ai_agent/sandbox/core/sandbox.py` —— FileSandbox 主类
  - `src/ai_agent/sandbox/core/context.py` —— SandboxContext 上下文管理
  - `src/ai_agent/sandbox/guards/path_guard.py` —— PathGuard 路径守卫
  - `src/ai_agent/sandbox/guards/content_guard.py` —— ContentGuard 内容守卫
  - `src/ai_agent/sandbox/guards/policy_guard.py` —— PolicyGuard 策略守卫
  - `src/ai_agent/sandbox/backends/virtual_fs.py` —— VirtualFileSystem 虚拟文件系统
  - `src/ai_agent/sandbox/loaders/skill_loader.py` —— SkillSandboxLoader
  - `src/ai_agent/sandbox/middleware/sandbox_middleware.py` —— SandboxMiddleware HITL 中间件
  - `src/ai_agent/sandbox/sandbox_pool.py` —— SandboxPool 用户隔离 + 池管理 + 预热

- **沙箱安全特性**
  - 路径遍历防护（`../` 逃逸检测）
  - 恶意代码检测（eval/exec/subprocess/os.system 等）
  - Prompt 注入检测（ignore instructions/DAN jailbreak 等）
  - 敏感信息检测（API Key/私钥/数据库连接字符串）
  - 虚拟文件系统（内存操作，不实际访问磁盘）
  - 白名单/黑名单操作控制
  - HITL 人工审批机制
  - 用户级沙箱隔离（每个用户独立实例）
  - 沙箱池预热机制

- **容器级沙箱**
  - `Dockerfile.sandbox` —— 沙箱容器镜像
  - `docker-compose.sandbox.yml` —— 沙箱部署配置
  - 只读文件系统、禁止提权、非 root 用户、资源限制

- **沙箱单元测试** —— 48 个测试
  - `tests/unit/sandbox/test_path_guard.py` —— 13 个测试
  - `tests/unit/sandbox/test_content_guard.py` —— 13 个测试
  - `tests/unit/sandbox/test_virtual_fs.py` —— 13 个测试
  - `tests/unit/sandbox/test_sandbox_pool.py` —— 9 个测试

### Changed（变更）

- **DeepAgent 架构完善** —— `deep_novel_agent.py` 集成沙箱机制

### Documentation（文档）

- `docs/SANDBOX.md` —— Docker 沙箱安全配置详解
- `scripts/run_in_sandbox.sh` —— 沙箱运行脚本

---

## [0.5.0] - 2026-08-20

### Added（新增）

- **DeepAgent 架构改造** —— 重大架构升级
  - `src/ai_agent/agents/deep_novel_agent.py` —— 使用 `create_deep_agent()` 重构
  - `skills/novel-craft/SKILL.md` —— NovelCraft Skill 定义
  - 内置 Middleware：TodoList/Filesystem/SubAgent/HITL/Skills/Memory
  - 内置 Subagents：narrator（大纲规划）、scribe（章节写作）、stylist（风格分析）
  - `tests/unit/agents/test_deep_novel_agent.py` —— DeepAgent 架构测试

- **Subagent 任务委派功能** —— 完整实现
  - `src/ai_agent/schemas/task.py` —— Task/TaskInput/TaskOutput/TaskResult 模型
  - `src/ai_agent/agents/subagent.py` —— Subagent 执行器和 TaskExecutor
  - `src/ai_agent/tools/subagent_task.py` —— task_tool 和 parallel_task_tool
  - 支持独立上下文、单个报告返回、并行执行、特殊化配置
  - `tests/unit/tools/test_subagent_task.py` —— 20 个单元测试

- **敏感词检测中间件** —— AC-5 完成
  - `src/ai_agent/guardrail/sensitive_word_filter.py` —— 敏感词检测核心模块
  - `tests/unit/guardrail/test_sensitive_word_filter.py` —— 15 个单元测试

### Architecture（架构调整）

- **双轨架构并存**：
  - 原始架构：`novel_agent.py`（LangGraph StateGraph）
  - 新架构：`deep_novel_agent.py`（DeepAgent create_deep_agent）
- **Task 工具链**：`task_tool()` → Subagent → TaskOutput 单个报告
- **并行执行**：`parallel_task_tool()` → asyncio.gather → TaskResult 汇总报告

---

## [0.4.0] - 2026-08-20

### Added（新增）

- **Phase 3: 高级功能** —— 完成
  - 多章节创作流程（`total_chapters` 参数，章节递增）
  - `POST /api/export` —— txt 格式导出端点
  - `GET /api/sessions` —— 列出历史会话
  - `GET /api/sessions/{thread_id}` —— 获取会话详情
  - `PUT /api/outline` —— 大纲编辑端点
  - `src/ai_agent/exporters/` —— 导出模块
  - `src/ai_agent/agents/state.py` —— 新增 `total_chapters`, `completed_chapters`, `delegation_result` 字段
  - `tests/integration/api/test_phase3_features.py` —— Phase 3 集成测试

---

## [0.3.0] - 2026-08-19

### Added（新增）

- **Phase 2: 风格学习与记忆** —— 完成 AC-1 ~ AC-6 全部验收标准
  - `src/ai_agent/agents/stylist_agent.py` —— Stylist Agent 风格控制
  - `src/ai_agent/rag/qdrant_client.py` —— Qdrant 向量存储客户端
  - `src/ai_agent/rag/embeddings.py` —— Embedding 生成
  - `src/ai_agent/rag/style_analyzer.py` —— LLM 风格特征提取
  - `src/ai_agent/main.py` —— `/api/styles`, `/api/preferences` 端点
  - `src/ai_agent/agents/novel_agent.py` —— Scribe Agent 风格约束注入
  - `tests/integration/test_style_learning.py` —— 风格学习集成测试（11/11 通过）
  - `tests/unit/rag/test_style_learning_unit.py` —— 风格学习单元测试（4/4 通过）

---

## [0.2.0] - 2026-08-17

### Added（新增）

- **NovelCraft PoC Phase 1 完成** —— 小说创作 AI Agent 多智能体系统
  - `src/ai_agent/agents/novel_agent.py` —— Narrator + Scribe Agent 实现
  - `src/ai_agent/main.py` —— FastAPI SSE 接口（/api/chat, /api/resume, /api/session）
  - `src/ai_agent/config/settings.py` —— LLM + Redis 配置
  - `src/ai_agent/schemas/chat.py` —— Pydantic 请求/响应 DTO
  - `tests/integration/api/test_novel_craft_e2e.py` —— E2E 集成测试（7/7 通过）
  - `tests/integration/api/test_checkpointer.py` —— Checkpointer 测试（4/4 通过）
- **Redis Checkpointer** —— LangGraph RedisSaver + MemorySaver 降级
- **HITL 中断机制** —— interrupt/resume 完整实现
- **Docker Compose 配置** —— redis + backend + frontend 一键启动
- **GitHub Actions CI** —— lint / type / redlines / pytest / cov
- **Alembic 数据库迁移** —— `001_initial_schema` 7 张表

### Fixed（修复）

- `Security(auto_error=False)` → HTTPBearer 不支持该参数，已移除
- 测试文件缺失 `user_id` 字段，已补全
- JSON 请求体重复 `user_id` key 已去重

---

## [0.1.0] - 2026-07-31

### Added（新增）

- **Harness Engineering 约束环境初始化**
- **`.claude/Claude.md`** —— AI 编码全局约束（红线 R1-R16）
- **`.harness/rules/`** —— 4 个规则文件（工程结构 / 编码 / 开发流程 / AI 特殊红线）
- **`.harness/agents/`** —— 4 个 agent（owner / planner / coder / reviewer）
- **`.harness/skills/`** —— 7 个 skill
- **`.harness/wiki/`** —— 4 个 wiki + 3 个 agent-templates
- **`scripts/`** —— 工具脚本（check_red_lines.py, init_db.sql 等）
- **`pyproject.toml`** + **`Makefile`** + **`docker-compose.yml`** + **`.env.example`** + **`.python-version`**
- **`docs/`** + **`README.md`** + **`origin-prompt.md`** + **`CHANGELOG.md`**

---

## 版本对照表

| 版本 | 日期 | 主要变更 |
| --- | --- | --- |
| 0.5.0 | 2026-08-20 | DeepAgent 架构改造 + Subagent 任务委派 |
| 0.4.0 | 2026-08-20 | Phase 3: 多章节/导出/会话管理 |
| 0.3.0 | 2026-08-19 | Phase 2: 风格学习与记忆 |
| 0.2.0 | 2026-08-17 | Phase 1: Narrator + Scribe Agent + HITL |
| 0.1.0 | 2026-07-31 | Harness Engineering 约束环境初始化 |

---

*本文档采用 Keep a Changelog 1.1.0。任何变更请在 [Unreleased] 段追加。*
