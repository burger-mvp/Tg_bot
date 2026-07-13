-- Основные пользователи бота.
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    phone_number TEXT,
    role TEXT,
    language_code VARCHAR(2) CHECK (language_code IN ('ru', 'en', 'ar') OR language_code IS NULL)
);

-- Задел для публикаций, которые будут добавлены в следующих частях бота.
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    media_ids TEXT,
    description TEXT,
    status TEXT,
    published_at TIMESTAMP
);
