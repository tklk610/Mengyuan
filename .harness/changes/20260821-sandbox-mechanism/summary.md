# 20260821-sandbox-mechanism — 文件操作沙箱机制

> 状态：completed
> 创建：2026-08-21
> 发布版本：v1.1.0
> Owner：Harness Engineer
> TAPD：none
> branch：main
> commit：-

## 需求描述

为 NovelCraft 项目实现文件操作沙箱机制，保护系统免受恶意操作和误操作的影响。

## 实现内容

### 沙箱架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FileSandbox                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 1: PathGuard - 路径守卫                                             │
│  • 路径遍历防护（../）                                                  │
│  • 允许/禁止路径列表                                                    │
│  • 系统敏感路径保护                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 2: ContentGuard - 内容守卫                                        │
│  • 恶意代码检测                                                        │
│  • Prompt 注入检测                                                     │
│  • 敏感信息检测                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 3: PolicyGuard - 策略守卫                                        │
│  • 白名单/黑名单操作控制                                                │
│  • 操作配额限制                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 4: VirtualFS - 虚拟文件系统                                       │
│  • 内存操作，不实际访问磁盘                                            │
│  • 操作审计日志                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 5: SkillSandboxLoader - Skill 安全加载                            │
│  • SKILL.md 内容扫描                                                   │
│  • frontmatter 验证                                                    │
│  • 签名验证（可选）                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 6: SandboxMiddleware - HITL 中间件                                │
│  • 危险操作拦截                                                       │
│  • 人工审批触发                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/ai_agent/sandbox/__init__.py` | 沙箱模块入口 |
| `src/ai_agent/sandbox/core/sandbox.py` | FileSandbox 主类 |
| `src/ai_agent/sandbox/core/context.py` | SandboxContext 上下文 |
| `src/ai_agent/sandbox/guards/path_guard.py` | PathGuard 路径守卫 |
| `src/ai_agent/sandbox/guards/content_guard.py` | ContentGuard 内容守卫 |
| `src/ai_agent/sandbox/guards/policy_guard.py` | PolicyGuard 策略守卫 |
| `src/ai_agent/sandbox/backends/virtual_fs.py` | VirtualFileSystem 虚拟文件系统 |
| `src/ai_agent/sandbox/loaders/skill_loader.py` | SkillSandboxLoader |
| `src/ai_agent/sandbox/middleware/sandbox_middleware.py` | SandboxMiddleware |

### 安全特性

| 特性 | 默认值 | 说明 |
|------|--------|------|
| virtual_mode | True | 虚拟模式，不实际写磁盘 |
| allowed_paths | ./skills, ./prompts/templates, ./workspace, ./exports | 允许路径 |
| denied_paths | ./.git, ./.venv, ./src/ai_agent/config | 禁止路径 |
| scan_malicious | True | 扫描恶意代码 |
| scan_injection | True | 扫描注入攻击 |
| quarantine_suspicious | True | 隔离可疑内容 |
| hitl_enabled | True | 启用人工审批 |

### 操作权限矩阵

| 操作 | 默认权限 | 说明 |
|------|----------|------|
| read | ✅ 允许 | 读取文件 |
| write | ⚠️ 需审批 | 写入文件 |
| edit | ⚠️ 需审批 | 编辑文件 |
| delete | ❌ 禁止 | 删除文件 |
| load_skill | ✅ 允许 | 加载 Skill |
| delegate_task | ⚠️ 需审批 | 任务委派 |

## 回滚方案

- 删除 `src/ai_agent/sandbox/` 目录
- 恢复 `deep_novel_agent.py` 到之前版本
