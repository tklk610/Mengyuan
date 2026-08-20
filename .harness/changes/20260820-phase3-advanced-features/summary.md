# 20260820-phase3-advanced-features — Phase 3: 高级功能

> 状态：completed
> 创建：2026-08-20
> Owner：Harness Engineer
> TAPD：none
> branch：feat/phase3-advanced-features
> commit：-

## 需求描述

实现 Phase 3 高级功能：
1. 多章节管理 - 支持创作多章节小说
2. 导出服务 - txt/epub/pdf 格式导出
3. 历史会话管理 - 会话持久化与恢复
4. 大纲编辑 - 用户可修改 AI 生成的大纲
5. 敏感内容检测 - 内容安全过滤

## 验收标准

- [x] AC-1: 用户可创作多章节小说（当前仅支持第1章）
- [x] AC-2: 创作完成的小说可导出为 txt 文件
- [x] AC-3: 用户可查看并加载历史会话
- [x] AC-4: 用户可在大纲生成后进行编辑修改
- [x] AC-5: 草稿内容通过敏感词检测

## 优先级

Must: AC-1, AC-2, AC-3
Should: AC-4
Could: AC-5

## 影响范围

| 类别 | 现有资产 | 变更 |
|------|----------|------|
| Agent | `novel_agent.py` | 多章节流程改造 |
| API | `main.py` | 新增导出/历史会话端点 |
| DB | PostgreSQL | Session 表 |
| Export | `exporters/` | 新增导出模块 |

## 风险与依赖

- 多章节状态管理复杂性
- 大文件导出可能超时

## 回滚方案

- 代码回滚到上一版本
- 删除 Session 表中相关记录
