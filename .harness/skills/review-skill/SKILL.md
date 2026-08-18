# 代码评审技能（review-skill）

## 概述
规范化代码评审，确保代码质量 + AI 红线 + 架构合规。

## 触发条件
- MR / PR 发起时
- Stage 6 流水线执行

## 前置条件
- 已经过 Stage 5（单元测试通过）
- 已经过 CI（ruff / mypy / pytest）

## 评审角色
| 角色 | 关注点 |
| --- | --- |
| **Owner**（必须） | 红线 / 业务正确性 / 影响范围 |
| **Reviewer A** | 编码规范 / 性能 / 安全 |
| **Reviewer B**（可选） | 测试覆盖率 / 可观测性 |

## 评审清单

### A. 规范层（机械可扫）
- [ ] ruff check 0 violation
- [ ] ruff format 0 diff
- [ ] mypy strict 0 error
- [ ] pytest 覆盖率 ≥ 80%（新增代码）
- [ ] 命名符合规范（snake_case / PascalCase）
- [ ] 文件放置符合 `工程结构规范.md`

### B. 架构层
- [ ] 依赖方向正确（api → service → repository → model）
- [ ] 没有跨模块内部实现导入
- [ ] ORM / SQL 抽象清晰
- [ ] Pydantic Schema 与 ORM 解耦
- [ ] Prompt 走外部化 YAML

### C. AI 红线层（强约束）
- [ ] **R9 HITL**：所有对外副作用工具都接 `interrupt`
- [ ] **R10 Prompt 注入**：无 f-string 拼接、`from_template` 已用
- [ ] **R11 Token 全链路**：每次 LLM 调用结束有 `TokenCounter.track()`
- [ ] **R12 PII 脱敏**：用户输入 / 日志 / 审计 三处都过 `redact()`
- [ ] **R13 事实校验**：RAG 引用 + 业务规则校验器到位
- [ ] **R14 模型降级链**：`MODEL_FALLBACK_CHAIN` 配置 + 故障演练
- [ ] **R15 配额硬拒绝**：80% / 100% 双阈值测试
- [ ] **R16 变更留痕**：`summary.md` 完备

### D. 业务层
- [ ] 验收标准全部满足
- [ ] 边界场景覆盖（空 / 超长 / 异常）
- [ ] 错误返回格式 `{code, message, data}` 统一
- [ ] 错误信息不泄露敏感
- [ ] 日志关键路径都有埋点

### E. 可观测层
- [ ] trace_id / request_id 全链路贯通
- [ ] 关键指标（延迟、错误率、token 用量）已埋点
- [ ] 告警阈值定义在 `config/monitoring.py`

## 评审结论
- 🟢 通过
- 🟡 建议改进（不阻塞）
- 🟥 必须修改（阻塞）

## 输出
- 在 GitHub / GitLab MR 上写评审意见
- 在 `.harness/changes/{feat}/review.md` 留一份评审记录

## 下一步
通过 → **Stage 7 集成测试**
