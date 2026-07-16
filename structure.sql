-- Счётчик для автоматической нумерации магазинов
CREATE SEQUENCE IF NOT EXISTS shop_counter START WITH 1;

-- Основные пользователи бота.
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    phone_number TEXT,
    role VARCHAR(20) NOT NULL DEFAULT 'user'
        CHECK (role IN ('user', 'admin', 'super_admin', 'trusted_seller')),
    language_code VARCHAR(2) CHECK (language_code IN ('ru', 'en') OR language_code IS NULL),
    username TEXT,
    name TEXT,
    registered_at TIMESTAMPTZ,
    shop_name TEXT,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Очередь модерации, отложенных публикаций и повторов через семь дней.
-- UUID формируется в Python, поэтому расширения PostgreSQL не требуются.
CREATE TABLE IF NOT EXISTS post_queue (
    id UUID PRIMARY KEY,
    author_telegram_id BIGINT NOT NULL REFERENCES users (telegram_id),
    author_role VARCHAR(20) NOT NULL
        CHECK (author_role IN ('user', 'admin', 'super_admin', 'trusted_seller')),
    language_code VARCHAR(2) NOT NULL CHECK (language_code IN ('ru', 'en')),
    -- Элементы: {"type": "video" | "document" | "photo", "file_id": "..."}.
    media_file_ids JSONB NOT NULL CHECK (jsonb_typeof(media_file_ids) = 'array'),
    description TEXT NOT NULL,
    post_kind VARCHAR(32) NOT NULL
        CHECK (post_kind IN ('engine_only', 'engine_with_transmission', 'body')),
    price_data JSONB NOT NULL CHECK (jsonb_typeof(price_data) = 'object'),
    post_text TEXT NOT NULL,
    status VARCHAR(32) NOT NULL
        CHECK (status IN ('pending_moderation', 'queued', 'publishing', 'published', 'duplicate_publishing', 'rejected')),
    approved_at TIMESTAMPTZ,
    scheduled_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    duplicate_due_at TIMESTAMPTZ,
    moderation_chat_id BIGINT,
    moderation_message_id BIGINT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS post_queue_ready_for_publication_idx
    ON post_queue (approved_at, created_at)
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS post_queue_duplicate_idx
    ON post_queue (duplicate_due_at)
    WHERE status = 'published';
