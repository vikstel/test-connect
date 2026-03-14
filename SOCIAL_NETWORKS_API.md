# Social Networks API — Руководство по подключению

## Telegram Bot API

- **Auth:** Bot token от @BotFather
- **Library:** `python-telegram-bot>=21` (`pip install python-telegram-bot`)
- **Методы:** `bot.send_message(chat_id, text)`, `send_photo`, `send_video`, `send_media_group`
- **Для каналов:** бот должен быть администратором канала
- **Rate limit:** 30 msg/sec к разным чатам, 1 msg/sec к одному чату
- **Docs:** https://core.telegram.org/bots/api

### Получение секретов

1. Открыть Telegram, найти **@BotFather**
2. Отправить `/newbot` → ввести имя бота → ввести username (должен заканчиваться на `bot`)
3. BotFather вернёт **Bot Token** — это и есть `TELEGRAM_BOT_TOKEN`

**Получить `chat_id` канала:**
- Добавить бота в канал как администратора
- Переслать любое сообщение из канала боту **@userinfobot** — он вернёт chat_id
- Для каналов chat_id начинается с `-100`

```env
TELEGRAM_BOT_TOKEN=123456789:AABBCCDDEEFFaabbccddeeff
TELEGRAM_CHAT_ID=-1001234567890   # для каналов начинается с -100
```

---

## VK API

- **Auth:** OAuth 2.0 access_token (user token с правами `wall`)
- **Library:** `vk_api` (`pip install vk_api`)
- **Метод:** `wall.post` → POST `https://api.vk.com/method/wall.post`
- **Scope:** `wall`, `photos`, `video`
- **Docs:** https://dev.vk.com/ru/method/wall.post

### Регистрация приложения (VK ID)

1. Войти через **VK Бизнес ID**: https://bid.vk.com/
2. Перейти в кабинет сервиса авторизации: https://id.vk.ru/about/business/go/
3. **Мои приложения → Добавить приложение**: https://id.vk.com/about/business/go/accounts/300345/create-app
4. Заполнить:
   - Название приложения
   - Платформа: **Web**
   - Базовый домен (например `yourdomain.com`)
   - Доверенный redirect URL (например `https://yourdomain.com/auth`)
5. Нажать **Создать приложение**

После создания в разделе **Приложение → Информация о приложении** будут доступны:
- **ID приложения** (`client_id`) — для настройки SDK
- **Защищённый ключ** (`client_secret`) — для серверных запросов
- **Сервисный ключ доступа** — для вызова методов API ВКонтакте (back-2-back)

> ⚠️ Для полного доступа к ключам и настройкам нужно подтвердить бизнес-профиль в VK Бизнес ID. Без верификации приложение будет заблокировано через 60 дней.

**Получить access_token пользователя:** https://vk.com/dev/authcode (Implicit Flow) или через `vk_api` auth

```env
VK_ACCESS_TOKEN=vk1.a.xxxxx
VK_OWNER_ID=-123456789   # отрицательное число для группы/паблика
VK_CLIENT_ID=12345678
VK_CLIENT_SECRET=xxxxx
VK_SERVICE_KEY=xxxxx
```

---

## Одноклассники (OK.ru) API

- **Auth:** OAuth 2.0 access_token + подпись запросов
- **Подпись:** `sig = MD5(sorted_params + MD5(access_token + secret_key))`
- **Library:** нет официального Python SDK → `requests`
- **Метод:** `mediatopic.post` → POST `https://api.ok.ru/fb.do`
- **Attachment:** JSON-структура с типами (text, photo, movie, link, poll)
- **Scope:** `GROUP_CONTENT`, `PHOTO_CONTENT`, `LONG_ACCESS_TOKEN`
- **Docs:** https://apiok.ru/dev/methods/rest/mediatopic/mediatopic.post

### Регистрация и получение ключей

> ⚠️ Создание новых приложений перенесено в **VK Mini Apps**: https://dev.vk.com

1. **Получить права разработчика:** https://ok.ru/devaccess (нужен аккаунт OK с привязанным email)
2. **Создать приложение:** https://ok.ru/vitrine/myuploaded → «В разработке» → «Добавить приложение»
3. Заполнить: название, имя в ссылке (латиница), описание
4. **Добавить платформу OAuth** (нужна для автопостинга и авторизации):
   - Ссылка на страницу (необязательно)
   - Список разрешённых `redirect_uri`
5. После создания **на email придут ключи**: `application_key` и `secret_key`

### Получение access_token

1. Открыть настройки приложения: https://ok.ru/vitrine/myuploaded → выбрать приложение → «Изменить настройки приложения» (нужен секретный ключ из письма)
2. Внизу страницы настроек найти блок **«Вечный access_token»**
3. Сгенерировать пару `access_token` + `session_secret_key`

```env
OK_ACCESS_TOKEN=xxxxx
OK_SESSION_SECRET_KEY=xxxxx          # session_secret_key из настроек приложения
OK_APPLICATION_KEY=ABCDEFGHIJKLMN   # public key (из письма или настроек)
OK_SECRET_KEY=xxxxx                  # secret key (из письма)
OK_GROUP_ID=123456789               # ID группы (без знака)
```

---

## Facebook Pages API (Graph API v25.0)

- **Auth:** OAuth 2.0, Page Access Token
- **Library:** `facebook-sdk` (`pip install facebook-sdk`) или `requests`
- **Метод:** POST `/{page_id}/feed` с полем `message`
- **Для фото:** POST `/{page_id}/photos` с полем `source` (multipart)
- **Permissions:** `pages_manage_metadata`, `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
- **Base URL:** `https://graph.facebook.com/v25.0/`
- **Docs:** https://developers.facebook.com/docs/pages-api/getting-started

### Получение секретов

1. **Создать приложение:** https://developers.facebook.com/apps → Create App → выбрать тип **Business**
2. В настройках приложения: **Settings → Basic** → скопировать `App ID` и `App Secret`
3. **Получить User Access Token** (с нужными правами):
   - Открыть Graph Explorer: https://developers.facebook.com/tools/explorer
   - Выбрать своё приложение → выдать permissions: `pages_manage_metadata`, `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
   - Нажать **Generate Access Token** → авторизоваться
4. **Получить Page Access Token и Page ID:**
   - В Graph Explorer выполнить запрос: `GET /me/accounts`
   - В ответе найти нужную страницу — там будут `id` (Page ID) и `access_token` (Page Access Token)

> ⚠️ User Access Token краткосрочный (~1ч). Для постоянной работы нужен Long-Lived Token: обменять через `GET /oauth/access_token?grant_type=fb_exchange_token`

```env
FACEBOOK_PAGE_ACCESS_TOKEN=EAAxxxxx
FACEBOOK_PAGE_ID=123456789012345
```

---

## Instagram Graph API

- **Auth:** OAuth 2.0 через Facebook Login
- **Требования:** Business или Creator аккаунт Instagram, привязанный к Facebook Page
- **Library:** `requests` (нет официального Python SDK)
- **Двухшаговый процесс постинга:**
  1. POST `/{ig-user-id}/media` — создать контейнер (поля: `image_url` или `video_url`, `caption`)
  2. POST `/{ig-user-id}/media_publish` — опубликовать (`creation_id` из шага 1)
- **Для видео:** добавить `media_type=REELS` или `media_type=VIDEO`
- **Permissions:** `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`
- **Ограничение:** изображение должно быть по публичному URL (не local file!)
- **Docs:** https://developers.facebook.com/docs/instagram-platform/content-publishing

### Получение секретов

1. **То же приложение что и Facebook** — заходить на https://developers.facebook.com/apps
2. В приложении: **Add Product → Instagram Graph API**
3. **Привязать Instagram аккаунт** к Facebook Page (в настройках Facebook Page → Instagram)
4. **Получить Instagram User ID и Access Token:**
   - В Graph Explorer: https://developers.facebook.com/tools/explorer
   - Добавить permissions: `instagram_basic`, `instagram_content_publish`
   - Запрос: `GET /me/accounts` → найти страницу → скопировать Page Access Token
   - Запрос: `GET /{page-id}?fields=instagram_business_account` → получить `instagram_business_account.id` — это и есть `INSTAGRAM_USER_ID`
5. **Access Token** — тот же Page Access Token, что и для Facebook (если аккаунты связаны)

> ⚠️ Изображение для постинга должно быть доступно по публичному HTTPS URL — локальные файлы не принимаются. При разработке используйте ngrok или загрузку на временный хостинг.

```env
INSTAGRAM_ACCESS_TOKEN=EAAxxxxx   # Page Access Token (тот же что Facebook)
INSTAGRAM_USER_ID=17841400000000000
```

---

## X (Twitter) API v2

- **Auth:** OAuth 2.0 PKCE (User Context) или OAuth 1.0a
- **Library:** `tweepy` (`pip install tweepy`)
- **Метод:** POST `https://api.x.com/2/tweets` с полем `text`
- **Для медиа:** сначала загрузить через v1.1 media upload endpoint
- **Scopes:** `tweet.write`, `tweet.read`, `users.read`, `offline.access`
- **Rate limit:**
  - Free tier — 17 постов/24ч (очень ограничен)
  - Pay-per-usage — оплата за кредиты, без месячной подписки
- **Docs:** https://docs.x.com/x-api/posts/manage-tweets/introduction

### Получение секретов

1. **Зарегистрироваться как разработчик:** https://developer.x.com/en/portal/petition/essential/basic-info
   - Нужен аккаунт X с подтверждённым email и номером телефона
   - Заполнить форму: описание использования API
2. **Создать Project и App:** https://developer.x.com/en/portal/projects-and-apps → New Project → New App
3. В настройках App перейти на вкладку **Keys and Tokens:**
   - **API Key & Secret** (`TWITTER_API_KEY`, `TWITTER_API_SECRET`) — генерируются при создании, сохранить сразу
   - **Bearer Token** (`TWITTER_BEARER_TOKEN`) — там же, кнопка Generate
   - **Access Token & Secret** (`TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`) — кнопка Generate в разделе «Authentication Tokens»; токены выдаются от имени владельца аккаунта
4. В настройках App: **User authentication settings** → включить OAuth 1.0a или OAuth 2.0, выставить permissions **Read and Write**

> ⚠️ При создании App сразу сохраните API Key & Secret — они показываются только один раз. Если потеряли — нужно регенерировать.

```env
TWITTER_API_KEY=xxxxx
TWITTER_API_SECRET=xxxxx
TWITTER_ACCESS_TOKEN=xxxxx
TWITTER_ACCESS_TOKEN_SECRET=xxxxx
TWITTER_BEARER_TOKEN=xxxxx
```

---

## Яндекс Дзен

- ⚠️ **Публичного API для постинга НЕТ**
- **Официальный способ:** Партнёрский API (закрытый, требует договор с Яндексом)
- **Доступный workaround: RSS-импорт**
  - Дзен может подтягивать контент с RSS-ленты блога
  - Настройка: Дзен Studio → Импорт из RSS → указать URL вашей RSS-ленты
  - Дзен проверяет ленту раз в несколько часов
- **В приложении:** `zen_poster.py` генерирует `static/rss.xml`, доступный по URL приложения

```env
# Дзен не требует токенов — используется RSS
ZEN_RSS_FEED_TITLE=Мой Дзен Канал
ZEN_AUTHOR_NAME=Автор
```

---

## Общие замечания

1. **Никогда не коммитьте токены в git** — используйте `.env` файл
2. **Refresh tokens:** у Facebook и Instagram токены истекают → нужно обновлять через long-lived token
3. **Webhook vs polling:** для тестирования достаточно прямых API вызовов
4. **Media hosting для Instagram:** нужен публичный URL изображения/видео (можно использовать ngrok для локальной разработки)
