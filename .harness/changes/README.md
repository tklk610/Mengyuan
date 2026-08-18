# 变更追踪

> 所有架构级变更、功能开发、Bug 修复的入口。每个变更在 `changes/{feat-name}/` 下创建一个目录，包含 `summary.md`（必填）等文件。

## 目录结构

```
.harness/changes/
├── README.md                  # 本文件
├── templates/
│   ├── summary.template.md    # 变更概述（必填）
│   ├── tasks.template.md      # 任务拆分（必填）
│   ├── design.template.md     # 方案设计（可选）
│   └── review.template.md     # 评审记录（合入前必填）
└── {feat-name}/
    ├── summary.md             # 必填：变更概述（按 summary.template）
    ├── tasks.md               # 必填：任务拆分（按 tasks.template）
    ├── design.md              # 可选：方案设计（按 design.template）
    ├── topology.md            # Agent 拓扑（如涉及）
    ├── prompt-diff.md         # Prompt 变更（如涉及）
    ├── eval-result.json       # 评估报告（如涉及）
    ├── review.md              # 必填：评审记录（按 review.template）
    └── rollback.md            # 必填：回滚方案
```

## 命名规范

- 用 kebab-case：`add-refund-flow` / `fix-orchestrator-timeout`
- 动词开头：`add-` / `fix-` / `refactor-` / `migrate-` / `optimize-`
- **时间戳前缀** `{YYYYMMDD}-` 用于人类快速辨识新旧，不建议删减
- **commit-id / 工单号** 在 `summary.md` frontmatter 中填入，用于精准追溯（见下方）

> **追溯字段**（写在 `summary.md` frontmatter 中）：
> - `TAPD`：工单号（如 TAPD-10923），需求阶段创建目录后填入；无工单则写 `none`
> - `branch`：关联分支名，编码阶段填入
> - `commit`：合入 main/master 时由 CI 或 Owner 填入

## 生命周期

```
draft → in-progress → review → staging → production → archived
```

| 状态 | 含义 | 谁操作 |
| --- | --- | --- |
| `draft` | 草稿 | Owner |
| `in-progress` | 实施中 | Engineer |
| `review` | 评审中 | Reviewer |
| `staging` | 预发 | Owner |
| `production` | 已上线 | Owner |
| `archived` | 归档 | Owner |

## 模板

| 模板文件 | 用途 | 对应产物 |
| --- | --- | --- |
| `templates/summary.template.md` | 变更概述（必填） | `{feat-name}/summary.md` |
| `templates/tasks.template.md` | 任务拆分（必填） | `{feat-name}/tasks.md` |
| `templates/design.template.md` | 方案设计（可选） | `{feat-name}/design.md` |
| `templates/review.template.md` | 评审记录（合入前必填） | `{feat-name}/review.md` |

## 红线

1. 🔴 所有架构级变更必须有 summary.md
2. 🔴 Prompt 变更必须有 prompt-diff.md
3. 🔴 Agent 变更必须有 topology.md
4. 🔴 上线前必须有 review.md + eval-result.json
5. 🔴 必须有 rollback.md
