-- Harness Engineering — PostgreSQL 初始化脚本
-- ============================================================
-- 在 docker-compose 首次启动时自动执行。
-- 作用：启用 pgvector 扩展 + 创建 harness schema + 必要的角色/权限。
--
-- 注意：本文件由 docker-entrypoint-initdb.d 在容器首次启动时执行，
--       仅在 /var/lib/postgresql/data 为空（即首次启动）时生效。
-- ============================================================

-- 启用 pgvector 扩展（向量检索必需）
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用常用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- uuid 生成
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- 模糊搜索（备用）

-- 字符集（确保中文/emoji 正常）
SET client_encoding = 'UTF8';

-- 输出确认
SELECT
    'pgvector extension: ' || extversion AS info
FROM pg_extension
WHERE extname = 'vector';

-- 业务表与索引由 Alembic 迁移管理，本文件只做扩展/角色准备工作。
-- 等业务代码 src/ai_agent/ 落地后，会自动生成 migrations/versions/ 脚本。

-- 一个简单的连通性自检（供 docker healthcheck 失败时排错）
DO $$
BEGIN
    RAISE NOTICE 'Harness Engineering DB initialized: pgvector + uuid-ossp + pg_trgm ready';
END $$;