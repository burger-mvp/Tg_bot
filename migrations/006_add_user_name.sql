-- Добавляет отображаемое имя пользователя для поиска и выгрузки.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS name TEXT;

UPDATE users
SET username = COALESCE(NULLIF(username, ''), 'Нет юзернейма'),
    name = COALESCE(NULLIF(name, ''), NULLIF(username, ''), shop_name, 'Нет юзернейма')
WHERE username IS NULL
   OR username = ''
   OR name IS NULL
   OR name = '';

UPDATE users
SET language_code = 'en'
WHERE language_code IS NOT NULL
  AND language_code NOT IN ('ru', 'en');

UPDATE post_queue
SET language_code = 'ru'
WHERE language_code NOT IN ('ru', 'en');
