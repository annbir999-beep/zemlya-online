# -*- coding: utf-8 -*-
"""Проверка живучести OAuth-токена Google Workspace CLI (gws).

Зачем: приложение в Google Auth Platform опубликовано (In production), поэтому
refresh-токен не должен протухать через 7 дней, как в testing-режиме. Скрипт
подтверждает это фактом — не статусом, а реальным вызовом API.

Что делает:
  1. `gws auth status` — есть ли refresh-токен, валиден ли ключ шифрования;
  2. `gws drive files list` — живой запрос к API (только чтение, 1 файл);
  3. шлёт итог в Telegram Анне и дописывает строку в лог рядом со скриптом.

Запуск: python -X utf8 tools/gws_token_check.py
Планировщик Windows: задача GwsTokenCheck на 10.08.2026 (неделя после публикации).
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

TG_ENV = Path.home() / ".claude" / "channels" / "telegram" / ".env"
CHAT_ID = "574728046"                       # личный chat_id Анны
LOG = Path(__file__).with_name("gws_token_check.log")
GWS = Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "@googleworkspace" / "cli" / "bin" / "gws.exe"


def _run(args: list[str]) -> tuple[int, str]:
    """Вызвать gws.exe напрямую — в задаче планировщика PATH может быть урезан."""
    p = subprocess.run([str(GWS), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _json_tail(out: str) -> dict:
    """Выдрать JSON-объект из вывода.

    gws пишет 'Using keyring backend' в stderr, а JSON — в stdout; после склейки
    вокруг объекта остаётся мусор, поэтому raw_decode, а не json.loads.
    """
    dec = json.JSONDecoder()
    start = out.find("{")
    while start != -1:
        try:
            obj, _ = dec.raw_decode(out[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        start = out.find("{", start + 1)
    return {}


def _notify(text: str) -> None:
    token = None
    if TG_ENV.exists():
        for line in TG_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not token:
        print("TELEGRAM_BOT_TOKEN не найден — только лог", file=sys.stderr)
        return
    data = json.dumps({"chat_id": CHAT_ID, "text": text}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()


def main() -> None:
    rc_status, out_status = _run(["auth", "status"])
    st = _json_tail(out_status)
    rc_api, out_api = _run(["drive", "files", "list",
                            "--params", '{"pageSize": 1, "fields": "files(name)"}'])

    api_ok = rc_api == 0 and '"files"' in out_api
    refresh = bool(st.get("has_refresh_token"))
    user = st.get("user", "?")

    if api_ok and refresh:
        text = (f"gws: токен жив\n{user}\n"
                f"refresh-токен на месте, Drive отвечает.\n"
                f"Публикация приложения сработала — переавторизация не нужна.")
    elif not api_ok:
        reason = _json_tail(out_api).get("error", {}).get("message") or out_api.strip()[:300]
        text = (f"gws: токен НЕ работает\n{user}\n"
                f"Ошибка API: {reason}\n\n"
                f"Лечится так: gws auth login --scopes "
                f'"https://www.googleapis.com/auth/drive,'
                f"https://www.googleapis.com/auth/gmail.modify,"
                f"https://www.googleapis.com/auth/spreadsheets,"
                f"https://www.googleapis.com/auth/documents,"
                f'https://www.googleapis.com/auth/calendar"\n'
                f"Если повторяется — проверь статус на "
                f"https://console.cloud.google.com/auth/audience?project=gws-cli-anna "
                f"(должно быть In production).")
    else:
        text = (f"gws: API отвечает, но refresh-токена нет\n{user}\n"
                f"Доступ пропадёт, когда истечёт access-токен. Стоит перелогиниться.")

    line = f"{datetime.now():%Y-%m-%d %H:%M}\tapi_ok={api_ok}\trefresh={refresh}\trc={rc_status}/{rc_api}"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)
    print(text)

    try:
        _notify(text)
    except Exception as e:                   # лог важнее доставки
        print(f"Telegram не доставил: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
