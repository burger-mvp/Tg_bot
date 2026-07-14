-- Поля для хранения username и даты первой записи, используемые в экспорте users.
-- Миграция безопасна для повторного запуска.
ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;

UPDATE users
SET created_at = COALESCE(created_at, registered_at, NOW())
WHERE created_at IS NULL;

ALTER TABLE users ALTER COLUMN created_at SET DEFAULT NOW();

