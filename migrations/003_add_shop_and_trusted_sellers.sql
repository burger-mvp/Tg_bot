-- Добавляем поле shop_name для идентификатора магазина/продавца
ALTER TABLE users ADD COLUMN IF NOT EXISTS shop_name TEXT;

-- Создаём счётчик для автоматической нумерации магазинов
CREATE SEQUENCE IF NOT EXISTS shop_counter START WITH 1;

-- Обновляем ограничение на роли, добавляя роль доверенного продавца
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check 
    CHECK (role IN ('user', 'admin', 'super_admin', 'trusted_seller'));

-- Обновляем ограничение на языки, добавляя новые языки
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_language_code_check;
ALTER TABLE users ADD CONSTRAINT users_language_code_check 
    CHECK (language_code IN ('ru', 'en', 'ar', 'fa', 'ur', 'hi', 'bn') OR language_code IS NULL);

-- Обновляем ограничения в таблице post_queue
ALTER TABLE post_queue DROP CONSTRAINT IF EXISTS post_queue_author_role_check;
ALTER TABLE post_queue ADD CONSTRAINT post_queue_author_role_check 
    CHECK (author_role IN ('user', 'admin', 'super_admin', 'trusted_seller'));

ALTER TABLE post_queue DROP CONSTRAINT IF EXISTS post_queue_language_code_check;
ALTER TABLE post_queue ADD CONSTRAINT post_queue_language_code_check 
    CHECK (language_code IN ('ru', 'en', 'ar', 'fa', 'ur', 'hi', 'bn'));
