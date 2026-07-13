-- Выполните этот файл в PostgreSQL Railway перед деплоем версии с очередью.
-- Он не удаляет пользователей и не затрагивает старую таблицу posts.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS registered_at TIMESTAMPTZ;

-- Пользователи, зарегистрированные в предыдущей версии, не считаются новыми:
-- им не будут повторно отправляться уведомления администраторам.
UPDATE users
SET registered_at = NOW()
WHERE phone_number IS NOT NULL
  AND registered_at IS NULL;

CREATE TABLE IF NOT EXISTS post_queue (
    id UUID PRIMARY KEY,
    author_telegram_id BIGINT NOT NULL REFERENCES users (telegram_id),
    author_role VARCHAR(20) NOT NULL
        CHECK (author_role IN ('user', 'admin', 'super_admin')),
    language_code VARCHAR(2) NOT NULL CHECK (language_code IN ('ru', 'en', 'ar')),
    -- Элементы: {"type": "video" | "document", "file_id": "..."}.
    media_file_ids JSONB NOT NULL CHECK (jsonb_typeof(media_file_ids) = 'array'),
    description TEXT NOT NULL,
    post_kind VARCHAR(32) NOT NULL
        CHECK (post_kind IN ('engine_only', 'engine_with_transmission', 'body')),
    price_data JSONB NOT NULL CHECK (jsonb_typeof(price_data) = 'object'),
    post_text TEXT NOT NULL,
    status VARCHAR(32) NOT NULL
        CHECK (status IN ('pending_moderation', 'queued', 'publishing', 'published', 'duplicate_publishing')),
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

-- На случай, если деплой произошел во время отправки в старой версии приложения.
UPDATE post_queue
SET status = 'queued',
    scheduled_at = NOW()
WHERE status = 'publishing';

UPDATE post_queue
SET status = 'published'
WHERE status = 'duplicate_publishing';
