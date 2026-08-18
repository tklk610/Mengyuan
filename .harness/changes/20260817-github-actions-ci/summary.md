# 20260817-github-actions-ci

> 状态：production
> 创建：2026-08-17
> Owner：Harness Engineer
> TAPD：none
> branch：-
> commit：-

## 需求描述

创建 `.github/workflows/ci.yml`，实现完整的 CI/CD 流水线，覆盖质量门禁（lint / type / redlines）和测试（unit / integration / coverage）。

## 验收标准

- [ ] AC-1: push 到 main/maintain 分支自动触发 CI
- [ ] AC-2: PR 自动触发 CI
- [ ] AC-3: README.md 添加 CI badge

## 优先级

Must

## 影响范围

| 类别 | 现有资产 | 变更 |
| --- | --- | --- |
| CI | `.github/workflows/ci.yml` | 新增；4 个 job：quality-gates / unit-tests / integration-tests / coverage |
| Doc | `README.md` | 新增 CI badge |
| DB | - | 无 |

## 冲突报告

| 级别 | 冲突 | 缓解 |
| --- | --- | --- |
| 🟢 | 无 | |

## 任务拆分

1. [Engineer] 创建 `.github/workflows/` 目录
2. [Engineer] 编写 `ci.yml`（4 个 job）
3. [Engineer] README.md 添加 CI badge
4. [Reviewer] 代码评审

## 风险与依赖

- 需要仓库已在 GitHub，后续 push 时 CI 才真正运行

## 回滚方案

- 删除 `.github/workflows/ci.yml`，README 移除 badge

## 评估基线

- `git log` 确认 CI workflow 存在且 job 定义完整

## 变更日志

| 日期 | 阶段 | 操作 | commit |
| --- | --- | --- | --- |
| 2026-08-17 | production | 完成 | - |
