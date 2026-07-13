-- Выполните миграцию один раз в PostgreSQL Railway ПЕРЕД деплоем новой версии.
-- NULL остается допустимым: зарегистрированные ранее пользователи увидят
-- выбор языка при следующем вызове команды /start.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS language_code VARCHAR(2);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_language_code_check'
          AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT users_language_code_check
            CHECK (language_code IN ('ru', 'en', 'ar') OR language_code IS NULL);
    END IF;
END $$;
