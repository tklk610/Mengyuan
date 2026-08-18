# T10 NovelCraft PoC 验收文档

**版本**：v0.1.0-PoC
**日期**：2026-08-14
**状态**：待验收

---

## 一、交付范围

本次 PoC 交付基于 `D:\Project\Harness_Engineering` 代码库，交付物为 NovelCraft 多 Agent 协作写小说系统的最小可演示版本。

---

## 二、功能验收标准

### 2.1 Narrator Agent（剧情规划）

| 验收项 | 验收条件 | 测试覆盖 |
|--------|---------|---------|
| 大纲生成 | 给定题材+需求，Agent 返回结构化 JSON 大纲（三幕） | 集成测试覆盖 |
| 题材支持 | 支持仙侠/修仙/奇幻/悬疑/言情/科幻 6 种题材 | Schema 测试覆盖 |
| 对话记忆 | 多轮对话中保持上下文 | 代码审查确认 |
| 外部化 Prompt |Narrator prompt 模板在 YAML 文件中，非硬编码 | 代码审查确认 |

### 2.2 Scribe Agent（正文撰写）

| 验收项 | 验收条件 | 测试覆盖 |
|--------|---------|---------|
| 章节生成 | 给定大纲+章节号，生成 2000-4000 字正文 | 集成测试覆盖 |
| 草稿输出 | 正文流式返回（分块 SSE） | 集成测试覆盖 |
| 章节续写 | 支持多章节顺序生成 | 代码审查确认 |

### 2.3 HITL 中断机制

| 验收项 | 验收条件 | 测试覆盖 |
|--------|---------|---------|
| accept 路径 | 用户选择后章节完成，graph 到达 END | 集成测试覆盖 |
| rewrite 路径 | 重新生成当前章节 | 代码审查确认 |
| restart 路径 | 清空状态重新开始 | 代码审查确认 |
| 中断恢复 | `/api/resume` 正确恢复 checkpoint | 集成测试覆盖 |
| 双重中断防护 | 无中断时调用 `/api/resume` 返回 400 | 集成测试覆盖 |

### 2.4 SSE 流式 API

| 验收项 | 验收条件 | 测试覆盖 |
|--------|---------|---------|
| outline 事件 | Narrator 完成后立即推送 | 集成测试覆盖 |
| draft_delta 事件 | Scribe 正文分块推送（50词/块）| 代码审查确认 |
| complete 事件 | 章节完成后推送 | 集成测试覆盖 |
| status 事件 | 中断时重复调用返回状态事件 | 集成测试覆盖 |
| error 事件 | 异常时返回错误描述 | 集成测试覆盖 |

### 2.5 会话管理

| 验收项 | 验收条件 | 测试覆盖 |
|--------|---------|---------|
| session 创建 | UUID 格式 thread_id，幂等创建 | 集成测试覆盖 |
| 健康检查 | `/health` 返回 200 | 集成测试覆盖 |
| 状态隔离 | 不同 thread_id 会话状态独立 | 代码审查确认 |

---

## 三、质量门槛验收

| 门槛 | 标准 | 实际结果 |
|------|------|---------|
| Ruff lint | 0 errors | ✅ 通过 |
| MyPy 类型检查 | 0 errors（34 source files）| ✅ 通过 |
| AI 红线扫描 | 0 errors | ✅ 通过 |
| Pytest | 61/61 通过 | ✅ 通过（新增 test_checkpointer.py 2项）|
| 覆盖率 | >= 80% | ⚠️ 待测量 |

---

## 四、测试清单

### 4.1 集成测试（14 项）

| 文件 | 测试数 | 结果 |
|------|--------|------|
| `tests/integration/api/test_novel_craft_e2e.py` | 7 | 7/7 ✅ |
| `tests/integration/api/test_checkpointer.py` | 2 | 2/2 ✅（Redis Checkpointer 状态恢复 + MemorySaver 兜底）|
| `tests/integration/test_agent_quality_gate.py` | 5 | 5/5 ✅ |

### 4.2 单元测试（47 项）

| 文件 | 测试数 | 覆盖规则 |
|------|--------|---------|
| `tests/unit/guardrail/test_r10_prompt_injection.py` | 5 | R10 |
| `tests/unit/guardrail/test_r11_token_counter.py` | 6 | R11 |
| `tests/unit/guardrail/test_r12_pii_redaction.py` | 5 | R12 |
| `tests/unit/guardrail/test_r14_fallback_chain.py` | 3 | R14 |
| `tests/unit/guardrail/test_r15_budget_hard_reject.py` | 3 | R15 |
| `tests/unit/guardrail/test_r1_llm_timeout.py` | 9 | R1 |
| `tests/unit/guardraft/test_r3_tool_idempotency.py` | 4 | R3 |
| `tests/unit/llm/test_factory.py` | 5 | LLM 工厂 |
| `tests/unit/schemas/test_chat.py` | 4 | Schema |
| `tests/unit/agents/test_state.py` | 2 | NovelState TypedDict |

### 4.3 AI 红线规则覆盖

| 规则 | 说明 | 测试覆盖 |
|------|------|---------|
| R1 | LLM 必须 timeout | ✅ |
| R2 | I/O 操作 tenacity 重试 | ⚠️ 警告（建议）|
| R3 | Tool 幂等性 | ✅ |
| R4 | 日志 PII 过滤 | ⚠️ 警告（建议）|
| R5 | 禁止裸 print | ✅ 代码审查 |
| R6 | 敏感配置不硬编码 | ✅ |
| R7 | API 统一 DTO | ✅ |
| R10 | f-string 用户输入防注入 | ✅ |
| R11 | TokenCounter.track() | ⚠️ 警告（建议）|
| R12 | PII redact() 处理 | ⚠️ 警告（建议）|
| R14 | Fallback 降级链 | ⚠️ 警告（建议）|
| R15 | 配额硬拒绝 | ✅ |
| R16 | 变更记录 | ⚠️ 框架层 |

---

## 五、数据

### 5.1 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.11 | |
| langchain | >= 0.3.0 | |
| langgraph | >= 0.3.0 | |
| FastAPI | >= 0.111 | |
| httpx | >= 0.27 | 集成测试用 |

### 5.2 配置

| 环境变量 | 说明 |
|----------|------|
| `MINIMAX_API_KEY` | MiniMax API Key（测试/开发用）|
| `OPENAI_API_KEY` | OpenAI API Key（备用）|
| `ANTHROPIC_API_KEY` | Anthropic API Key（备用）|

---

## 六、已知限制（PoC 范围外）

| 限制 | 影响 | 生产化建议 |
|------|------|-------------|
| ~~内存 session~~ | ~~进程重启丢失~~ | ✅ **已解决**：RedisSaver |
| ~~无 Alembic 迁移~~ | ~~Schema 变更无法追踪~~ | ✅ **已解决**：Alembic + 7表 |
| ~~无 CI/CD~~ | ~~手动部署~~ | ✅ **已解决**：GitHub Actions |
| ~~HITL accept 路径 bug~~ | ~~accept 无法正确完成章节~~ | ✅ **已解决**：`choice.get("choice")` |
| Prompt 模板无版本管理 | 模板直接改文件 | 引入版本 tag（v1/v2）|
| 无多用户/权限 | 所有用户共享会话 | JWT 认证 + user_id 隔离 |
| 单 HTML 前端 | 无 React/Next.js | 前端重构 |
| LLM API key 环境变量明文 | 无 Vault | 接入 AWS Secret Manager / Vault |
| 无数据导出 | 草稿无法持久化 | 接入 PostgreSQL + 文件存储 |
| 无 RAG | 风格/情节无向量检索 | 接入 Qdrant / pgvector |
| 无多租户隔离 | 会话数据混杂 | 租户 ID 字段接入 |
| LLM API key 缺失则崩溃 | 无降级提示 | 接入健康检查 + graceful degradation |

---

## 七、验收结论

| 角色 | 签字 |
|------|------|
| PO / Owner | ⬜ |
| AI Reviewer | ⬜ |
| Harness Engineer | ⬜ |

**PoC 状态**：✅ 可交付演示，⏳ 生产化需完成上节限制项
