# Prompt 调优技能（prompt-iteration）

## 概述
规范化 Prompt 工程：版本化、A/B、回归测试、漂移检测。

## 触发条件
- 新增 Prompt 模板
- 修改 Prompt 模板
- LLM 行为出现漂移 / 衰减
- 重大业务变更

## 流程

### 1. Prompt 规范

所有 Prompt 放 `prompt-templates/`（或 `src/ai_agent/prompt/templates/`）：

```yaml
# chat_system_v3.yaml
name: chat_system
version: 3
status: canary            # canary | stable | deprecated
description: |
  通用对话系统提示词，v3 强化了对未知问题的拒答能力。
model: gpt-4o-mini
temperature: 0.0
variables:
  - name: agent_name
    required: true
    type: str
  - name: user_language
    required: true
    type: str
  - name: retrieved_docs
    required: false
    type: list[dict]
template: |
  你是 {{ agent_name }}，一个专业的 AI 助手。
  用户使用 {{ user_language }}沟通，请用相同语言回答。
  
  【参考资料】
  {% for doc in retrieved_docs %}
  - {{ doc.content }}
  {% endfor %}
  
  【规则】
  1. 只能基于参考资料回答，未知请明说。
  2. 禁止输出参考资料之外的事实。
```

### 2. 版本管理

- `v1`, `v2`, `v3` ...
- `status` 三态：
  - `canary`：灰度 5% 流量
  - `stable`：默认版本（最多一个）
  - `deprecated`：已弃用，30 天后删除

### 3. A/B 测试

```python
# 业务调用方只需要传 alias
prompt = PromptLoader.load(alias="chat_system")  # 自动选 stable 或 canary
# A/B 比例由 PromptLoader 从配置读
```

### 4. 回归测试

`tests/unit/prompt/` 下放 `test_chat_system_v3.py`：

```python
import pytest
from ai_agent.prompt.loader import PromptLoader
from langchain_openai import ChatOpenAI
from ai_agent.llm.factory import get_llm
import respx

@pytest.mark.unit
class TestChatSystemV3:
    """Prompt chat_system v3 的回归测试"""

    @pytest.fixture
    def template(self):
        return PromptLoader.load(name="chat_system", version="3")

    def test_template_must_include_retrieved_docs_variable(self, template):
        assert "retrieved_docs" in template.variables

    def test_template_must_forbid_external_facts(self, template):
        assert "只能基于参考资料" in template.template

    async def test_llm_call_with_template_should_not_hallucinate(self, template):
        # mock LLM 返回 + 校验 prompt 内容
        ...
```

### 5. 漂移检测

- 每次生产调用记录：`prompt_hash + completion + score`
- 周期性任务（每日）：跑 `prompt-regression` 测试集，对比 `score.mean` 是否显著下滑
- 阈值下滑 > 5% → 自动告警

### 6. 评估指标

| 指标 | 计算 | 适用 |
| --- | --- | --- |
| **Faithfulness** | LLM 答案中可被 reference 支撑的比例 | RAG |
| **Answer Relevance** | 答案与 query 相关度 | 通用 |
| **Context Precision** | 检索 topK 中相关 chunk 比例 | RAG |
| **Hallucination Rate** | 1 - Faithfulness | RAG |
| **Deflection Rate** | 模型主动拒答比例 | 客服 |

### 7. 工具

- **RAGAS**（Python）—— 自动算上述指标
- **Promptfoo**（Node）—— Prompt 批量 A/B
- **LangSmith**—— 在线追踪 + 反馈标注

## 模板变更流程
1. 在 `prompt-templates/` 新增 `chat_system_v4.yaml`
2. 同步在 `tests/unit/prompt/test_chat_system_v4.py` 加回归测试
3. 配置 `canary=5%`
4. 跑 3 天评测
5. 切到 `stable`，旧版改 `deprecated`

## 禁止
- ❌ 修改 prompt 不写测试
- ❌ 业务代码硬编码大段 prompt
- ❌ `canary` 跳过评测直接上 stable

## 下一步
Prompt 变更 → **Stage 4 重新编码**（连锁触发）
