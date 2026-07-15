# coding: utf-8
"""Данные локализации для всех поддерживаемых языков."""

RU_TEXTS = {
    "choose_language": "Выберите язык интерфейса:",
    "language_saved": "Язык сохранен.",
    "enter_phone": "Нажмите кнопку ниже, чтобы отправить номер телефона.",
    "share_phone": "📱 Отправить номер телефона",
    "send_contact_only": "Пожалуйста, отправьте номер через кнопку «Отправить номер телефона».",
    "foreign_contact": "Можно отправить только собственный контакт через кнопку ниже.",
    "registration_complete": "Регистрация завершена.",
    "start_registration": "🚀 Начать",
    "start_prompt": "Нажмите кнопку «🚀 Начать», чтобы пройти регистрацию.",
    "welcome_user": "Добро пожаловать! Выберите действие в меню ниже.",
    "welcome_admin": "Добро пожаловать! Вам доступны создание постов и админ-панель.",
    "welcome_super_admin": "Добро пожаловать, супер-администратор!",
    "welcome_trusted_seller": "Добро пожаловать! Ваши посты публикуются автоматически без модерации.",
    "create_post": "Создать пост",
    "admin_panel": "Админ-панель",
    "super_admin_panel": "Супер админ панель",
    "admin_panel_hint": "Для создания публикации нажмите «Создать пост». Посты администраторов сразу попадут в очередь.",
    "super_admin_panel_hint": "Нажмите «Создать пост» для прямой публикации. Заявки обычных пользователей приходят в этот чат с кнопками «Выложить», «Редактировать» и «Отклонить».",
    "language_required": "Сначала отправьте /start и завершите регистрацию.",
    "access_denied": "У вас нет доступа к этому действию.",
    "send_media": "Загрузите видео или фотографии (от 1 до 30 файлов). Можно отправить альбом. Когда закончите, нажмите кнопку внизу экрана.",
    "media_saved": "Медиа сохранено: {count} из {max_count}.",
    "send_media_only": "На этом шаге принимаются фото, видео и видеофайлы MP4, MOV, MKV, AVI или WEBM. GIF-анимации, видеосообщения и другие файлы не подходят. После загрузки нажмите кнопку внизу.",
    "media_outside_post_creation": "Нет активного создания поста. Нажмите «Создать пост», дождитесь сообщения о загрузке медиа, затем отправьте фото или видео.",
    "media_not_expected": "Медиа сейчас не ожидается. Завершите текущий шаг сценария или отмените его и начните создание поста заново.",
    "media_expected": "На этом шаге нужно отправить медиафайл. Пожалуйста, загрузите фото или видео, либо нажмите кнопку завершения.",
    "media_too_large": "Файл слишком тяжелый! Telegram позволяет загружать файлы только до {max_size_mb} МБ. Пожалуйста, сожмите видео перед отправкой.",
    "no_media": "Сначала загрузите хотя бы одно фото или видео.",
    "media_limit": "Можно загрузить не более {max_count} медиафайлов.",
    "media_uploaded": "✅ Медиа загружены",
    "media_collection_complete": "Медиа загружены. Выберите категорию товара ниже.",
    "choose_category": "Выберите категорию товара:",
    "engine": "Двигатель / ДВС",
    "body": "Кузовное",
    "choose_engine_type": "Выберите комплектацию:",
    "engine_only": "Двигатель",
    "engine_with_transmission": "Двигатель с КПП",
    "enter_engine_price": "Введите цену двигателя в AED:",
    "enter_transmission_price": "Введите цену двигателя с КПП в AED:",
    "enter_body_description": "Введите описание:",
    "enter_body_price": "Введите цену в AED:",
    "enter_description": "Напишите описание:",
    "invalid_price": "Пожалуйста, введите только число (например, 15000) без букв и пробелов!",
    "description_empty": "Описание не должно быть пустым. Введите его еще раз.",
    "description_too_long": "Описание слишком длинное. Максимум: {max_length} символов.",
    "send_text_only": "Пожалуйста, отправьте описание обычным текстовым сообщением.",
    "cancel": "❌ Отмена",
    "post_cancelled": "Создание поста отменено.",
    "post_save_failed": "Не удалось сохранить пост. Мы записали ошибку в журнал. Попробуйте повторить через минуту или обратитесь к администратору.",
    "post_added_queue": "Пост добавлен в очередь публикации. Он будет отправлен в ближайший доступный слот.",
    "post_sent_for_moderation": "Пост отправлен супер-администратору на модерацию.",
    "moderation_delivery_failed": "Пост сохранен, но не удалось доставить его на модерацию. Супер-администратору нужно открыть бота и отправить /start.",
    "moderation_request": "Пост от пользователя ID: {author_id}. Проверьте материалы и выберите действие:",
    "approve": "✅ Выложить",
    "edit": "✏️ Редактировать",
    "reject": "🚫 Отклонить",
    "moderation_approved": "Пост одобрен и добавлен в очередь публикации.",
    "moderation_approve_failed": "Ошибка при одобрении поста.",
    "moderation_approve_failed_detail": "Ошибка при одобрении поста: {error}",
    "post_rejected": "Пост отклонен.",
    "post_rejected_notification": "❌ К сожалению, ваш пост был отклонён модератором. Вы можете создать новый пост с обновлённым содержимым.",
    "already_moderated": "Этот пост уже обработан или не найден.",
    "edit_prompt": "Отправьте исправленное описание. Видео/фото и рассчитанные цены останутся прежними.",
    "edit_prompt_with_description": "Пришлите исправленное описание. Вы можете скопировать текущее описание ниже: нажмите на него, вставьте в поле ввода, отредактируйте и отправьте мне. Видео/фото и рассчитанные цены останутся прежними.\n\n<code>{description}</code>",
    "post_updated": "Описание обновлено. Проверьте новую версию и выберите действие.",
    "set_trusted_seller": "🌟 Назначить доверенного продавца",
    "enter_shop_name_for_trust": "Введите Telegram ID, @username, имя пользователя или название магазина (например, Shop 7):",
    "shop_not_found": "Пользователь не найден. Введите Telegram ID, @username, имя или Shop из выгрузки users.",
    "trusted_seller_assigned": "✅ Пользователь {user_label} успешно назначен Доверенным продавцом!",
    "set_admin": "👤 Назначить администратора",
    "enter_telegram_id_for_admin": "Введите Telegram ID, @username, имя пользователя или название магазина (например, Shop 7):",
    "admin_assigned": "✅ Пользователь {user_label} успешно назначен Администратором!",
    "user_not_found": "Пользователь не найден. Введите Telegram ID, @username, имя или Shop из выгрузки users. Пользователь должен сначала пройти регистрацию через /start.",
    "view_queue": "📋 Просмотр очереди",
    "export_users": "📊 Выгрузить users",
    "queue_status": "📊 **Статус очереди публикаций**\n\n📝 Всего постов в очереди: {total}\n⏳ Ожидают публикации: {queued}\n✅ Опубликованы: {published}\n🔄 Ожидают дубликата: {waiting_duplicate}",
    "queue_list_header": "Ближайшие посты к публикации:",
    "queue_list_item": "{index}. {shop_name} — {scheduled_at}\n{description}",
    "queue_empty": "Очередь пуста. Все посты опубликованы.",
    "publication_queue_empty": "Очередь публикаций пуста.",
    "users_export_header": "📊 **Экспорт таблицы users**\n\nФайл содержит всех зарегистрированных пользователей.",
    "info_message": """🤖 **О боте KPP Motors**

Этот бот помогает продавцам автозапчастей публиковать товары в канале.

📋 **Основные функции:**
• Загрузка фото и видео товаров
• Автоматический расчёт цен с наценкой
• Публикация в канал по расписанию
• Мультиязычная поддержка

🚀 **Как пользоваться:**
1. Нажмите «Создать пост»
2. Загрузите фото/видео товара
3. Выберите категорию (Engine или кузовное)
4. Укажите цену в AED
5. Добавьте описание
6. Пост отправится на модерацию

💡 **Совет:** Вы можете загрузить до 30 медиафайлов в один пост. Цены округляются автоматически для красоты.

❓ Вопросы? Обратитесь к @Kpp_Motors""",
}

EN_TEXTS = {
    "choose_language": "Choose the interface language:",
    "language_saved": "Language saved.",
    "enter_phone": "Tap the button below to share your phone number.",
    "share_phone": "📱 Share phone number",
    "send_contact_only": "Please use the \"Share phone number\" button below.",
    "foreign_contact": "You can only share your own contact using the button below.",
    "registration_complete": "Registration completed.",
    "start_registration": "🚀 Start",
    "start_prompt": "Tap “🚀 Start” to complete registration.",
    "welcome_user": "Welcome! Choose an action from the menu below.",
    "welcome_admin": "Welcome! You can create posts and open the admin panel.",
    "welcome_super_admin": "Welcome, super administrator!",
    "welcome_trusted_seller": "Welcome! Your posts are published automatically without moderation.",
    "create_post": "Create post",
    "admin_panel": "Admin panel",
    "super_admin_panel": "Super admin panel",
    "admin_panel_hint": "Tap \"Create post\" to make a publication. Administrator posts go to the queue immediately.",
    "super_admin_panel_hint": "Tap \"Create post\" for a direct publication. Regular users' requests arrive in this chat with \"Publish\", \"Edit\" and \"Reject\" buttons.",
    "language_required": "First send /start and complete registration.",
    "access_denied": "You do not have access to this action.",
    "send_media": "Upload videos or photos (from 1 to 30 files). Albums are supported. Tap the button at the bottom when finished.",
    "media_saved": "Media saved: {count} of {max_count}.",
    "send_media_only": "Photos, videos and MP4, MOV, MKV, AVI, or WEBM video files are accepted here. GIF animations, video notes, and other files are not supported. Tap the button at the bottom after uploading.",
    "media_outside_post_creation": "There is no active post creation. Tap \"Create post\", wait for the media upload prompt, then send photos or videos.",
    "media_not_expected": "Media is not expected right now. Complete the current step or cancel it and start post creation again.",
    "media_expected": "Send a media file at this step. Please upload a photo or video, or tap the completion button.",
    "media_too_large": "The file is too large. Telegram allows files up to {max_size_mb} MB only. Please compress the video before sending it.",
    "no_media": "Upload at least one photo or video first.",
    "media_limit": "You can upload no more than {max_count} media files.",
    "media_uploaded": "✅ Media uploaded",
    "media_collection_complete": "Media uploaded. Choose the product category below.",
    "choose_category": "Choose the product category:",
    "engine": "Engine",
    "body": "Body parts",
    "choose_engine_type": "Choose the configuration:",
    "engine_only": "Engine only",
    "engine_with_transmission": "Engine with Gearbox",
    "enter_engine_price": "Enter the engine-only price in AED:",
    "enter_transmission_price": "Enter the engine with gearbox price in AED:",
    "enter_body_description": "Enter the description:",
    "enter_body_price": "Enter the price in AED:",
    "enter_description": "Write the description:",
    "invalid_price": "Please enter only a number (for example, 15000), without letters or spaces.",
    "description_empty": "The description cannot be empty. Enter it again.",
    "description_too_long": "The description is too long. Maximum: {max_length} characters.",
    "send_text_only": "Please send the description as a regular text message.",
    "cancel": "❌ Cancel",
    "post_cancelled": "Post creation cancelled.",
    "post_save_failed": "The post could not be saved. The error was recorded in the log. Try again in a minute or contact an administrator.",
    "post_added_queue": "The post was added to the publication queue. It will be sent in the next available slot.",
    "post_sent_for_moderation": "The post was sent to the super administrator for moderation.",
    "moderation_delivery_failed": "The post was saved, but could not be delivered for moderation. The super administrator must open the bot and send /start.",
    "moderation_request": "Post from user ID: {author_id}. Review the content and choose an action:",
    "approve": "✅ Publish",
    "edit": "✏️ Edit",
    "reject": "🚫 Reject",
    "moderation_approved": "The post was approved and added to the publication queue.",
    "moderation_approve_failed": "Could not approve the post.",
    "moderation_approve_failed_detail": "Could not approve the post: {error}",
    "post_rejected": "Post rejected.",
    "post_rejected_notification": "❌ Unfortunately, your post was rejected by the moderator. You can create a new post with updated content.",
    "already_moderated": "This post was already processed or was not found.",
    "edit_prompt": "Send the corrected description. Videos/photos and calculated prices will remain unchanged.",
    "edit_prompt_with_description": "Send the corrected description. You can copy the current description below: tap it, paste it into the input field, edit it and send it to me. Videos/photos and calculated prices will remain unchanged.\n\n<code>{description}</code>",
    "post_updated": "Description updated. Review the new version and choose an action.",
    "set_trusted_seller": "🌟 Assign trusted seller",
    "enter_shop_name_for_trust": "Enter Telegram ID, @username, user name or shop name (for example, Shop 7):",
    "shop_not_found": "User not found. Enter Telegram ID, @username, name or Shop from the users export.",
    "trusted_seller_assigned": "✅ User {user_label} has been successfully assigned as Trusted seller!",
    "set_admin": "👤 Assign administrator",
    "enter_telegram_id_for_admin": "Enter Telegram ID, @username, user name or shop name (for example, Shop 7):",
    "admin_assigned": "✅ User {user_label} has been successfully assigned as Administrator!",
    "user_not_found": "User not found. Enter Telegram ID, @username, name or Shop from the users export. The user must complete registration via /start first.",
    "view_queue": "📋 View queue",
    "export_users": "📊 Export users",
    "queue_status": "📊 **Publication queue status**\n\n📝 Total posts in queue: {total}\n⏳ Awaiting publication: {queued}\n✅ Published: {published}\n🔄 Awaiting duplicate: {waiting_duplicate}",
    "queue_list_header": "Next posts scheduled for publication:",
    "queue_list_item": "{index}. {shop_name} — {scheduled_at}\n{description}",
    "queue_empty": "Queue is empty. All posts have been published.",
    "publication_queue_empty": "Publication queue is empty.",
    "users_export_header": "📊 **Users table export**\n\nFile contains all registered users.",
    "info_message": """🤖 **About KPP Motors Bot**

This bot helps auto parts sellers publish products to the channel.

📋 **Main features:**
• Upload product photos and videos
• Automatic price calculation with markup
• Scheduled channel publishing
• Multilingual support

🚀 **How to use:**
1. Tap "Create post"
2. Upload product photos/videos
3. Choose category (Engine or body parts)
4. Enter price in AED
5. Add description
6. Post will be sent for moderation

💡 **Tip:** You can upload up to 30 media files in one post. Prices are automatically rounded for clarity.

❓ Questions? Contact @Kpp_Motors""",
}
