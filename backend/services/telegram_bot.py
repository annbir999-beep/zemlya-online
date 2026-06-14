"""
Telegram-бот для Торги Земли.

Принимает webhook-обновления от Telegram и обрабатывает команды:
  /start              — приветствие, инструкции
  /start <code>       — привязка аккаунта по deep-link коду
  /link <code>        — привязка аккаунта по коду из кабинета (ручной ввод)
  /help               — список команд
  /list               — мои активные фильтры (если привязан)
  /unlink             — отвязать аккаунт от этого Telegram

Привязка работает через одноразовый код, который пользователь получает в кабинете
сайта. Код хранится в Redis 10 минут.
"""
import secrets
from typing import Optional

import httpx
import redis.asyncio as redis_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.user import User
from models.alert import Alert


_REDIS: Optional[redis_async.Redis] = None
LINK_CODE_PREFIX = "tg_link:"
LINK_CODE_TTL = 600  # 10 минут
LINK_CODE_LENGTH = 8  # символов в URL-safe base64
SITE_URL = settings.SITE_URL


def _tg_client(timeout: int = 10) -> httpx.AsyncClient:
    """HTTP-клиент к api.telegram.org.

    Резолв api.telegram.org -> IPv4 захардкожен в docker-compose.yml через
    extra_hosts, потому что у docker-сети нет IPv6-маршрутизации, а AAAA
    резолв даёт ENETUNREACH.
    """
    return httpx.AsyncClient(timeout=timeout)


def get_redis() -> redis_async.Redis:
    global _REDIS
    if _REDIS is None:
        _REDIS = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
    return _REDIS


async def issue_link_code(user_id: int) -> str:
    """Генерирует одноразовый код привязки и сохраняет в Redis."""
    code = secrets.token_urlsafe(6).rstrip("-_=")[:LINK_CODE_LENGTH].upper()
    await get_redis().setex(LINK_CODE_PREFIX + code, LINK_CODE_TTL, str(user_id))
    return code


async def consume_link_code(code: str) -> Optional[int]:
    """Возвращает user_id и удаляет код. None если код не найден или истёк."""
    if not code:
        return None
    key = LINK_CODE_PREFIX + code.strip().upper()
    r = get_redis()
    pipe = r.pipeline()
    pipe.get(key)
    pipe.delete(key)
    user_id_raw, _ = await pipe.execute()
    if not user_id_raw:
        return None
    try:
        return int(user_id_raw)
    except (TypeError, ValueError):
        return None


async def send_message(
    chat_id: int | str,
    text: str,
    parse_mode: str = "Markdown",
    disable_web_page_preview: bool = True,
) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    async with _tg_client(timeout=10) as client:
        try:
            await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": disable_web_page_preview,
                },
            )
        except Exception as e:
            print(f"[telegram-bot] sendMessage error: {type(e).__name__}: {e}")


async def set_webhook(url: str, secret_token: Optional[str] = None) -> dict:
    """Устанавливает webhook у Telegram. Вызывать вручную при деплое."""
    payload = {"url": url, "drop_pending_updates": True}
    if secret_token:
        payload["secret_token"] = secret_token
    async with _tg_client(timeout=15) as client:
        r = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook",
            json=payload,
        )
        return r.json()


HELP_TEXT = (
    "*Торги Земли — Telegram-бот*\n\n"
    "Я присылаю уведомления о новых земельных лотах по вашим фильтрам.\n\n"
    "*Команды:*\n"
    "/link `КОД` — привязать аккаунт (код берётся в кабинете на сайте)\n"
    "/list — показать активные фильтры\n"
    "/unlink — отвязать этот Telegram от аккаунта\n"
    "/help — эта справка\n\n"
    f"Сайт: {SITE_URL}"
)


async def _bind_user(db: AsyncSession, user_id: int, chat_id: int) -> Optional[User]:
    """Прописывает chat_id пользователю по user_id (с переносом, если был привязан другой)."""
    chat_id_str = str(chat_id)

    # Если этот chat_id уже привязан к другому юзеру — освобождаем (один TG = один аккаунт)
    other = await db.execute(
        select(User).where(User.telegram_id == chat_id_str, User.id != user_id)
    )
    for u in other.scalars().all():
        u.telegram_id = None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.telegram_id = chat_id_str
    user.notification_telegram = True
    await db.commit()
    return user


async def _cmd_start(db: AsyncSession, chat_id: int, args: str, user: Optional[User]) -> None:
    if args:
        # /start <code> — deep-link привязка
        await _cmd_link(db, chat_id, args, user)
        return

    if user:
        await send_message(
            chat_id,
            f"Привет, *{user.name or user.email}*! Аккаунт уже привязан. Отправь /help, чтобы увидеть команды.",
        )
        return

    await send_message(
        chat_id,
        "👋 *Торги Земли* — агрегатор земельных аукционов.\n\n"
        f"Чтобы получать уведомления, зайди в кабинет на {SITE_URL}/dashboard, "
        "нажми *Привязать Telegram* и пришли мне код командой:\n"
        "`/link КОД`\n\n"
        "Команда /help — список всех команд.",
    )


async def _cmd_link(db: AsyncSession, chat_id: int, args: str, _user: Optional[User]) -> None:
    code = (args or "").strip().split()[0] if args else ""
    if not code:
        await send_message(chat_id, "Укажи код после команды, например: `/link AB12CD34`")
        return

    user_id = await consume_link_code(code)
    if not user_id:
        await send_message(
            chat_id,
            "❌ Код не найден или истёк. Получите новый код в кабинете на сайте.",
        )
        return

    user = await _bind_user(db, user_id, chat_id)
    if not user:
        await send_message(chat_id, "❌ Пользователь не найден. Попробуй ещё раз.")
        return

    await send_message(
        chat_id,
        f"✅ Готово! Аккаунт *{user.email}* привязан.\n"
        "Теперь ты будешь получать уведомления по своим фильтрам.\n\n"
        "/list — посмотреть активные фильтры",
    )


async def _cmd_help(_db: AsyncSession, chat_id: int, _args: str, _user: Optional[User]) -> None:
    await send_message(chat_id, HELP_TEXT)


async def _cmd_list(db: AsyncSession, chat_id: int, _args: str, user: Optional[User]) -> None:
    if not user:
        await send_message(
            chat_id,
            "Аккаунт не привязан. Получите код в кабинете и пришлите `/link КОД`.",
        )
        return

    result = await db.execute(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at.desc())
    )
    alerts = result.scalars().all()
    if not alerts:
        await send_message(
            chat_id,
            f"У тебя пока нет фильтров. Создать можно в кабинете: {SITE_URL}/dashboard",
        )
        return

    lines = [f"*Твои фильтры* — {len(alerts)} шт.\n"]
    for a in alerts[:15]:
        status = "🟢" if a.is_active else "⚪"
        lines.append(f"{status} `#{a.id}` {a.name} — {a.channel.value}")
    if len(alerts) > 15:
        lines.append(f"\n_...и ещё {len(alerts) - 15}_")
    await send_message(chat_id, "\n".join(lines))


async def _cmd_unlink(db: AsyncSession, chat_id: int, _args: str, user: Optional[User]) -> None:
    if not user:
        await send_message(chat_id, "Этот Telegram не привязан ни к одному аккаунту.")
        return
    user.telegram_id = None
    user.notification_telegram = False
    await db.commit()
    await send_message(chat_id, "Готово. Telegram отвязан, уведомления отключены.")


COMMANDS = {
    "/start": _cmd_start,
    "/link": _cmd_link,
    "/help": _cmd_help,
    "/list": _cmd_list,
    "/unlink": _cmd_unlink,
}


async def _handle_agent_callback(db: AsyncSession, callback: dict) -> None:
    """Inline-кнопки одобрения черновиков агентов (agent_pub:<id> / agent_skip:<id>).

    Доступно только админскому чату — кнопки шлются лишь туда, но проверяем
    отправителя на случай пересылки сообщения.
    """
    from core.config import settings as _settings

    callback_id = callback.get("id")
    data = callback.get("data") or ""
    from_id = str((callback.get("from") or {}).get("id") or "")
    msg = callback.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")

    async def answer(text: str, alert: bool = False) -> None:
        async with _tg_client(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{_settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text[:190], "show_alert": alert},
            )

    if from_id != str(_settings.ADMIN_TELEGRAM_CHAT_ID):
        await answer("Кнопка доступна только администратору")
        return

    action, _, run_id_raw = data.partition(":")
    try:
        run_id = int(run_id_raw)
    except ValueError:
        await answer("Некорректные данные кнопки")
        return

    from models.agent_run import AgentRun
    run = (await db.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one_or_none()
    if not run:
        await answer(f"Запуск #{run_id} не найден")
        return

    from services.agents.publishing import PublishError, approve_and_publish, skip_run
    try:
        if action == "agent_pub":
            result = await approve_and_publish(db, run)
        else:
            result = await skip_run(db, run)
    except PublishError as e:
        await answer(str(e), alert=True)
        return
    except Exception as e:
        print(f"[telegram-bot] agent callback error: {type(e).__name__}: {e}")
        await answer(f"Ошибка: {type(e).__name__}", alert=True)
        return

    await answer("Готово")
    # Убираем кнопки и дописываем итог под сообщением
    status_line = "✅ Опубликовано" if action == "agent_pub" else "❌ Пропущено"
    if chat_id and message_id:
        async with _tg_client(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{_settings.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup",
                json={"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}},
            )
            await client.post(
                f"https://api.telegram.org/bot{_settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"{status_line} (run #{run_id})\n{result}",
                      "disable_web_page_preview": True},
            )


async def process_update(db: AsyncSession, update: dict) -> None:
    """Точка входа для webhook. Парсит update от Telegram и вызывает обработчик команды."""
    callback = update.get("callback_query")
    if callback and (callback.get("data") or "").startswith(("agent_pub:", "agent_skip:")):
        await _handle_agent_callback(db, callback)
        return

    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return

    # Найти текущего пользователя по telegram_id (если уже привязан)
    user_result = await db.execute(select(User).where(User.telegram_id == str(chat_id)))
    user = user_result.scalar_one_or_none()

    # Парсим команду — поддержка /cmd@botname
    parts = text.split(maxsplit=1)
    cmd = parts[0].split("@", 1)[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handler = COMMANDS.get(cmd)
    if handler:
        try:
            await handler(db, chat_id, args, user)
        except Exception as e:
            print(f"[telegram-bot] handler error {cmd}: {type(e).__name__}: {e}")
            await send_message(chat_id, "Что-то пошло не так. Попробуй позже.")
        return

    # Любое другое сообщение — короткая подсказка
    await send_message(chat_id, "Не понял команду. Отправь /help.")
