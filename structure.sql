-- Основные пользователи бота.
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    phone_number TEXT,
    role TEXT
);

-- Задел для публикаций, которые будут добавлены в следующих частях бота.
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    media_ids TEXT,
    description TEXT,
    status TEXT,
    published_at TIMESTAMP
);
