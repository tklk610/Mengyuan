# 20260817-alembic-init

> 状态：production
> 创建：2026-08-17
> Owner：Harness Engineer
> TAPD：none
> branch：-
> commit：-

## 需求描述

初始化 Alembic 迁移框架，建立 `src/ai_agent/migrations/` 目录和首个版本脚本 `001_initial_schema.py`，对标 `NOVEL_CRAFT_PROJECT_PLAN.md` 第三节数据模型设计。

## 验收标准

- [ ] AC-1: `uv run alembic check` 通过
- [ ] AC-2: `uv run alembic history` 可查看版本历史
- [ ] AC-3: Makefile 新增 `db-migrate` / `db-migrate-down` / `db-migrate-history` 等 target

## 优先级

Must

## 影响范围

| 类别 | 现有资产 | 变更 |
| --- | --- | --- |
| Config | `alembic.ini` | 新增；sqlalchemy.url 指向 PostgreSQL |
| Migration | `src/ai_agent/migrations/` | 新增目录 + 4 个文件 |
| Migration | `src/ai_agent/migrations/versions/001_initial_schema.py` | 新增：users / projects / chapters / style_profiles / novel_samples / user_preferences / foreshadowing |
| Config | `Makefile` | 新增 db-migrate 等 6 个 target |
| Config | `.env.example` | 新增 DATABASE_URL 占位说明 |

## 冲突报告

| 级别 | 冲突 | 缓解 |
| --- | --- | --- |
| 🟢 | 无 | |

## 任务拆分

1. [Engineer] 安装 alembic 依赖
2. [Engineer] `alembic init src/ai_agent/migrations`
3. [Engineer] 配置 `alembic.ini`（sqlalchemy.url）
4. [Engineer] 重写 `env.py`（异步支持 + DATABASE_URL 环境变量覆盖）
5. [Engineer] 编写首个迁移脚本 `001_initial_schema.py`
6. [Engineer] Makefile 新增 db-migrate* targets
7. [Reviewer] 代码评审

## 风险与依赖

- 依赖 docker-compose 中 PostgreSQL 服务已启动
- `DATABASE_URL` 环境变量须在运行时正确设置

## 回滚方案

- `make db-migrate-down` 回退到上一个版本
- 手动：`psql`  DROP 所有表

## 评估基线

- `uv run alembic check` → 0 issues

## 变更日志

| 日期 | 阶段 | 操作 | commit |
| --- | --- | --- | --- |
| 2026-08-17 | production | 完成 | - |
