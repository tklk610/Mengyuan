# 编码技能（coding-skill）

## 概述
按规范实现功能代码，确保架构合规 + 可测试 + AI 红线 0 违反。

## 触发条件
- 进入开发 10 阶段流水线 **Stage 4**
- 已经过 Stage 1（需求）+ Stage 2（方案）

## 前置条件
- 需求分析文档 `.harness/changes/{feat}/summary.md`
- 方案设计文档（如有）
- 任务拆分 `.harness/changes/{feat}/tasks.md`
- 必要 Wiki（架构 / 数据模型 / 接口协议）

## 上下文准备（按需加载，不超过各 3 个）
- Rules：`编码规范.md` / `ai-special-rules.md` / `工程结构规范.md`
- Wiki：`架构设计.md` / `接口协议.md` / `agent-templates/*`
- 已有相关源码

## 执行步骤

### Step 1：定位落点
- 确认改动涉及的目录（按 `工程结构规范.md`）
- 列出**最多 3 个文件**作为起点（避免一上来铺开）

### Step 2：自上而下 / 自下而上 选型
- **自上而下**：从 API 路由 → Service → Repository 一路写
- **自下而上**：先写 Pydantic Schema → ORM 模型 → Repository → Service → API
- **AI 项目推荐**自下而上：先把数据契约敲死，再串

### Step 3：写代码（按"编码规范.md"）
- AI 单次变更 ≤ 40% 文件总数
- 每次完成后立即：
  - `ruff check src/ tests/`
  - `ruff format src/ tests/`
  - `mypy src/`（如已引入类型）
- 不确定就**立刻**问（"我不知道"）

### Step 4：自检 Checklist
- [ ] 依赖方向符合四层架构（api → service → repository → model）
- [ ] 所有公开函数有 type hint + docstring
- [ ] 所有外部调用套了 `with_retry()` / 熔断
- [ ] 所有 LLM 调用走 `llm.factory.get_llm()`
- [ ] Prompt 不硬编码（引用 YAML 模板名）
- [ ] 异常用自定义体系（`exception.*`）
- [ ] 日志用 structlog，PII 已脱敏
- [ ] AI 红线 8 条全过

### Step 5：暴露未知
代码里写了 `# TODO(owner): ……` 的位置必须在 summary.md "待澄清问题" 段同步列出。

## 下一步
编码完成 → **Stage 5 单元测试**（阅读 `unit-test-write/SKILL.md`）

## 禁止
- ❌ 在 `service/` 直接 import `sqlalchemy.*`
- ❌ `print()` 代替日志
- ❌ `try/except Exception: pass`
- ❌ `except: pass` 裸抛出
- ❌ 在单次生成里跨 ≥ 3 个不相关目录同时改
