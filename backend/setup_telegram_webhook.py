"""
Установка webhook у Telegram. Запускать вручную после настройки .env:

    docker exec sotka_backend python setup_telegram_webhook.py

Требует переменных окружения:
  TELEGRAM_BOT_TOKEN     — токен бота от @BotFather
  TELEGRAM_WEBHOOK_SECRET (опц.) — секрет для проверки подписи
  TELEGRAM_WEBHOOK_URL   — публичный URL: https://xn--e1adnd0h.online/api/telegram/webhook

Скрипт также печатает getMe (проверка токена и username бота).
"""
import asyncio
import os
import sys

import httpx

from core.config import settings
from services.telegram_bot import _tg_client


WEBHOOK_URL = os.environ.get(
    "TELEGRAM_WEBHOOK_URL",
    "https://xn--e1adnd0h.online/api/telegram/webhook",  # punycode для земля.online
)


async def main() -> int:
    if not settings.TELEGRAM_BOT_TOKEN:
        print("[setup-webhook] TELEGRAM_BOT_TOKEN не задан в .env", file=sys.stderr)
        return 1

    base = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
    async with _tg_client(timeout=15) as c:
        # 1) Проверка токена
        me = await c.get(f"{base}/getMe")
        me_json = me.json()
        if not me_json.get("ok"):
            print(f"[setup-webhook] getMe FAILED: {me_json}")
            return 2
        username = me_json["result"]["username"]
        print(f"[setup-webhook] Bot OK: @{username} (id={me_json['result']['id']})")
        if settings.TELEGRAM_BOT_USERNAME and settings.TELEGRAM_BOT_USERNAME.lstrip("@") != username:
            print(
                f"[setup-webhook] WARN: TELEGRAM_BOT_USERNAME='{settings.TELEGRAM_BOT_USERNAME}' "
                f"не совпадает с реальным '@{username}'. Поправь .env."
            )

        # 2) Установка webhook
        payload = {"url": WEBHOOK_URL, "drop_pending_updates": True}
        if settings.TELEGRAM_WEBHOOK_SECRET:
            payload["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET
        r = await c.post(f"{base}/setWebhook", json=payload)
        print(f"[setup-webhook] setWebhook -> {r.json()}")

        # 3) Регистрация команд для меню бота
        commands = [
            {"command": "start", "description": "Привет / привязка по deep-link"},
            {"command": "link", "description": "Привязать аккаунт по коду"},
            {"command": "list", "description": "Мои фильтры"},
            {"command": "unlink", "description": "Отвязать Telegram"},
            {"command": "help", "description": "Справка"},
        ]
        r = await c.post(f"{base}/setMyCommands", json={"commands": commands})
        print(f"[setup-webhook] setMyCommands -> {r.json()}")

        # 4) Проверка
        info = await c.get(f"{base}/getWebhookInfo")
        print(f"[setup-webhook] getWebhookInfo -> {info.json()}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
