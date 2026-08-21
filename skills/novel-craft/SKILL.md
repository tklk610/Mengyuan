---
name: novel-craft
description: NovelCraft 小说创作 AI Agent 系统，支持多章节创作、风格学习、HITL 审阅
---

# NovelCraft 小说创作技能

## 概述

NovelCraft 是一个基于多智能体协作的小说创作系统，支持：

- **多章节创作** - 支持创作多章节长篇小说
- **HITL 中断机制** - 草稿完成后需要人工审阅确认
- **风格学习** - 上传样本自动提取风格特征
- **导出功能** - 支持 txt 格式导出

## 架构

```
用户 -> Main Agent -> Narrator (大纲规划)
              |
         Scribe (正文写作)
              |
         Stylist (风格控制)
              |
         HITL 审阅 -> 接受/重写/重启
```

## 可用 Subagents

| Subagent | 职责 | 工具 |
|----------|------|------|
| narrator | 大纲规划 | plan_outline |
| scribe | 章节写作 | write_chapter |
| stylist | 风格分析 | analyze_style |

## 使用场景

### 1. 创作新小说

用户：写一个仙侠小说，主角是修仙弟子

### 2. 委派任务给 Subagent

使用 task 工具委派给 narrator 或 scribe

### 3. 风格学习

使用 task 工具委派给 stylist

## HITL 中断

当 scribe 完成草稿后，系统会触发 HITL 中断等待用户确认：

- approve - 接受草稿
- reject - 拒绝并要求重写
- edit - 修改后接受

## 导出

创作完成后，可以使用 /api/export 端点导出为 txt 格式。
