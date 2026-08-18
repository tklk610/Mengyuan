# Review — 评审记录（{feat-name}）

> 模板路径：`.harness/changes/templates/review.template.md`
> 复制到 `.harness/changes/{feat-name}/review.md` 后填写
> 评审人：@reviewer  时间：{YYYY-MM-DD}
> TAPD：{ticket-id}       # 工单号（如无则填 `none`）
> commit：{commit-hash}  # 合入 commit

## 评审结论

🟢 通过 / 🟡 通过（建议改进）/ 🟥 不通过（必须修改）

---

## A. 规范层（5 项）

- [ ] ruff check 0 violation
- [ ] ruff format 0 diff
- [ ] mypy strict 0 error
- [ ] pytest 覆盖率 ≥ 80%（新增代码）
- [ ] 命名 / 文件放置符合 `工程结构规范.md`

## B. 架构层（5 项）

- [ ] 依赖方向正确（api → service → repository → model）
- [ ] 没有跨模块内部实现导入
- [ ] ORM / SQL 抽象清晰
- [ ] Pydantic Schema 与 ORM 解耦
- [ ] Prompt 走外部化 YAML

## C. AI 红线（**R1-R16 必须逐条**）

- [ ] **R1** LLM 调用显式 timeout（`LLM_DEFAULT_TIMEOUT_SECONDS`）
- [ ] **R2** 外部调用套了 `with_retry()`（tenacity）
- [ ] **R3** 工具含 `idempotency_key`
- [ ] **R4** Prompt 外化（无字面量拼接）
- [ ] **R5** LLM 输出 `model_validate(...)` 包裹
- [ ] **R6** repository 层（无 service 直 SQL）
- [ ] **R7** 模块边界（无跨层 import）
- [ ] **R8** 金额字段 `int`（分）
- [ ] **R9** HITL（对外副作用工具在 LangGraph 中找到 `interrupt`）
- [ ] **R10** Prompt 注入（用 `PromptTemplate.from_template`）
- [ ] **R11** Token 计数（每次 LLM 调用结束有 `TokenCounter.track`）
- [ ] **R12** PII 脱敏（输入/日志/审计三处过 `redact`）
- [ ] **R13** 事实校验（RAG grounding 校验器到位）
- [ ] **R14** 降级链（`MODEL_FALLBACK_CHAIN` 在 config）
- [ ] **R15** 配额硬拒（`TokenCounter.check_before_call` + 429）
- [ ] **R16** 变更留痕（`summary.md` 6/7/8/9 段齐备）

## D. 业务层（5 项）

- [ ] 验收标准全部满足
- [ ] 边界场景覆盖（空 / 超长 / 异常）
- [ ] 错误返回格式 `{code, message, data}` 统一
- [ ] 错误信息不泄露敏感
- [ ] 日志关键路径都有埋点

## E. 可观测层（3 项）

- [ ] trace_id / request_id 全链路贯通
- [ ] 关键指标（延迟 / 错误率 / Token 用量）已埋点
- [ ] 告警阈值定义在 `config/monitoring.py`

---

## 🟥 必须修改（如有，逐条编号 + 修改建议 + 代码示例）

| # | 问题 | 修改建议 | 文件:行 |
| --- | --- | --- | --- |
| 1 | | | |
| 2 | | | |

## 🟡 建议改进（如有，NIT 必须合并同类项）

- ...

---

## Owner 签字

@name  时间：{YYYY-MM-DD HH:mm}

> **AI 红线层必须 Owner 也签字**