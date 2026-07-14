-- ВНИМАНИЕ: этот файл безвозвратно удаляет тестовых пользователей и все их посты.
-- Запускайте его вручную в Railway PostgreSQL только перед финальным релизом.
-- После выполнения первый зарегистрированный продавец получит Shop 1.
BEGIN;

DELETE FROM post_queue;
DELETE FROM users;
ALTER SEQUENCE shop_counter RESTART WITH 1;

COMMIT;
