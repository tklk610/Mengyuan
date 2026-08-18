# 单元测试编写技能（unit-test-write）

## 概述
为项目编写高质量、可维护的单元测试。

## 触发条件
- Stage 5 流水线（编码完成后）

## 技术栈

| 维度 | 工具 |
| --- | --- |
| 测试框架 | **pytest 8.x + pytest-asyncio** |
| Mock HTTP | **respx**（httpx 拦截） |
| Mock LLM | **respx** + JSON fixture |
| DB 测试 | **pytest-postgresql** 或 docker-compose 提供 |
| 覆盖率 | **pytest-cov** |
| Fixtures | `tests/conftest.py` |

## 测试组织

```
tests/
├── conftest.py
├── unit/
│   └── {mirror path}/test_*.py
├── integration/
├── e2e/
└── fixtures/
```

## 命名约定

- 测试文件：`test_*.py` 或 `*_test.py`
- 测试函数：`test_<行为>_<条件>_<期望>`
- 测试类：`Test<类名>`（PascalCase）
- 测试夹具命名：`fixture_<thing>`

## 测试模式

### 1. Service 层（最强要求）

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.unit
class TestChatService:
    """ChatService 业务逻辑测试"""

    @pytest.fixture
    def mock_llm(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_llm, mock_repo):
        return ChatService(llm=mock_llm, repo=mock_repo)

    async def test_chat_when_user_has_kb_should_use_rag_prompt(self, service, mock_llm, mock_repo):
        # Given
        mock_repo.get_user_kb_ids.return_value = ["kb1"]
        mock_llm.ainvoke.return_value = AIMessage(content="hi")

        # When
        result = await service.chat(user_id="u1", question="hi")

        # Then
        assert result.answer == "hi"
        assert "rag" in mock_llm.ainvoke.call_args.kwargs["messages"][0].content.lower()
```

### 2. API 层

```python
@pytest.mark.unit
class TestChatEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from ai_agent.main import app
        return TestClient(app)

    def test_chat_when_invalid_request_returns_400(self, client):
        # Given
        payload = {"question": ""}  # 缺 user_id

        # When
        resp = client.post("/api/v1/chat", json=payload)

        # Then
        assert resp.status_code == 422
        assert resp.json()["code"] != 200
```

### 3. LLM 调用（mock）

```python
import respx
from langchain_openai import ChatOpenAI

@pytest.mark.unit
async def test_llm_call_with_retry_should_retry_on_500():
    """LLM 500 → 必须重试 3 次后降级"""
    with respx.mock(base_url="https://api.openai.com") as rmock:
        rmock.post("/v1/chat/completions").mock(
            side_effect=[httpx.Response(500), httpx.Response(500), httpx.Response(200, json={"choices":[...]})]
        )

        llm = ChatOpenAI(model="gpt-4o-mini", max_retries=3)
        result = await llm.ainvoke("hi")

        assert rmock.calls.call_count == 3
```

### 4. AI Red Line 测试

```python
@pytest.mark.unit
async def test_pii_redaction_must_remove_email():
    from ai_agent.guardrail.pii import redact
    text = "联系邮箱：alice@example.com"
    assert "alice@example.com" not in redact(text)
    assert "[REDACTED:EMAIL]" in redact(text)

@pytest.mark.unit
async def test_token_quota_must_reject_when_exhausted(monkeypatch):
    from ai_agent.guardrail.token_counter import TokenCounter
    from ai_agent.exception.business import AgentBudgetExhaustedException

    monkeypatch.setenv("LLM_DAILY_TOKEN_QUOTA", "10")

    counter = TokenCounter()
    counter.consume(11)  # 超额

    with pytest.raises(AgentBudgetExhaustedException):
        await counter.check_before_call()
```

## 必须覆盖的场景

| 模块 | 必测场景 |
| --- | --- |
| LLM 调用 | timeout / 5xx / 4xx / 限流 / 重试 / 降级 |
| Agent | 工具调用成功 / 失败 / 重试 / HITL 中断 |
| RAG | 检索空 / topK 边界 / rerank 顺序 |
| Guardrail | PII / 注入 / Token 配额 |
| DB | 事务回滚 / 幂等性 / 并发 |
| API | 参数校验 / 异常返回 / SSE 流式断开 |

## 覆盖率要求

- 新增代码：**≥ 80%**（CI `--cov-fail-under=80`）
- 核心链路：**100%**
- AI 红线：每个红线至少 1 个测试

## 禁止
- ❌ 调用真实 LLM API（必须 mock）
- ❌ 真实数据库测试（除非开了 docker-compose）
- ❌ 一个测试函数 assert 多个不相关断言

## 下一步
测试通过 → **Stage 6 代码评审**
