-- 000-extensions.sql
-- Postgres extension bootstrap —— 全新環境（如 Cloud SQL for PostgreSQL）最先跑。
--
-- 本機 docker（pgvector/pgvector:pg17）這些多半已具備（映像自帶 + 後續 migration 建過），
-- 故此檔對既有 DB 是 idempotent no-op；它的目的是讓「空 DB」一次把相依 extension 開齊，
-- 避免後續 migration / 應用查詢踩到「extension 不存在」。
--
-- 對應實際用途（2026-06-16 盤點）：
--   vector     → public.manual_chunks.embedding / public.case_entries.embedding（知識庫 RAG 向量）
--   pg_trgm    → 中文子字串檢索 gin_trgm_ops（agent.memory_entry CR-0023 + 其他 trigram 索引）
--   pgcrypto   → gen_random_uuid()（多處 migration 預設值）
--   uuid-ossp  → uuid_generate_*（少數舊 migration）
--
-- Cloud SQL 備註：這些都是 Cloud SQL for PostgreSQL 支援的 extension，但需以
-- cloudsqlsuperuser 身分執行 CREATE EXTENSION（部署帳號通常即具備）。
-- pgvector 需 Cloud SQL PostgreSQL 版本支援（PG15+）；建實例時確認版本。

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
