from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://sotka:sotka_secret@db:5432/sotka"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "change_me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 часов — комфортный сеанс в кабинете
    REFRESH_TOKEN_EXPIRE_DAYS: int = 60
    ALGORITHM: str = "HS256"

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://земля.online",
        "https://xn--e1adnd0h.online",
        "https://www.xn--e1adnd0h.online",
    ]

    # Claude API
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = ""  # ProxyAPI/VseGPT base url для российских юзеров

    # Email
    SMTP_HOST: str = "smtp.yandex.ru"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""  # без @, например "ZemlyaOnlineBot"
    TELEGRAM_WEBHOOK_SECRET: str = ""  # для проверки X-Telegram-Bot-Api-Secret-Token

    # ЮКасса
    YUKASSA_SHOP_ID: str = ""
    YUKASSA_SECRET_KEY: str = ""

    # Scraping
    TORGI_GOV_DELAY: float = 1.0
    AVITO_DELAY: float = 3.0

    # Proxy for scraping
    PROXY_HOST: str = ""
    PROXY_USER: str = ""
    PROXY_PASS: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
