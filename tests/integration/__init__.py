"""Integration tests — 集成测试（通常需要 docker-compose 起 DB / Redis）。

按照 .harness/skills/unit-test-write/SKILL.md 的规范：
- 真实数据库 + 真实缓存 + mock 第三方 API
- 通过 pytest marker 'integration' 标记
"""
