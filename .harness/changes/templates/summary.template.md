# {feat-name}

> 状态：draft | in-progress | review | staging | production | archived
> 创建：{date}
> Owner：{owner}
> TAPD：{ticket-id}          # 工单号（如无则填 `none`）
> branch：{branch-name}      # 关联分支（编码阶段填入）
> commit：{commit-hash}      # 合入时由 CI 或 Owner 填入

## 需求描述

{用户原始需求 + 澄清后版本}

## 验收标准

- [ ] AC-1: ...
- [ ] AC-2: ...

## 优先级

Must / Should / Could

## 影响范围

| 类别 | 现有资产 | 变更 |
| --- | --- | --- |
| Agent | orchestrator | 新增 tech_support subagent |
| Tool | search_kb | 增强 top_k 范围 |
| Prompt | orchestrator@v1 | 新增 v2 |
| API | /api/v1/chat | 无 |
| DB | - | 无 |
| Config | - | 新增 TOOL_TIMEOUT_S |
| Deps | - | 无 |

## 冲突报告

| 级别 | 冲突 | 缓解 |
| --- | --- | --- |
| 🔴 | ... | ... |
| 🟡 | ... | ... |
| 🟢 | ... | ... |

## 任务拆分

1. [Architect] 拓扑设计（依赖 -）
2. [Agent Designer] State schema（依赖 1）
3. [Prompt Eng] orchestrator v2（依赖 1）
4. [Tool Builder] search_kb 增强（依赖 -）
5. [Eval Eng] 评估数据集（依赖 2,3,4）
6. [Reviewer] 评审（依赖 5）
7. [Owner] 合并（依赖 6）

## 风险与依赖

- ...

## 回滚方案

- 镜像回滚到 {previous_tag}
- DB 回滚脚本（如有）
- Prompt 回滚到 v{n-1}

## 评估基线

- 数据集：evals/datasets/{agent}_v{n}.jsonl
- 评分器：evals/graders/*
- Baseline：evals/reports/{agent}_baseline.json
- 当前：evals/reports/{agent}_{tag}.json

## 变更日志

| 日期 | 阶段 | 操作 | commit |
| --- | --- | --- | --- |
| {date} | draft | 创建 | - |
| ... | ... | ... | ... |
