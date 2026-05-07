from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db.database import engine, Base
# Импортируем модели чтобы Base.metadata знал о них (для create_all при первом старте)
from models import promo  # noqa: F401
from api import lots, users, alerts, ai, payments, subscriptions, telegram
from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Земля.ПРО — API",
    description="Агрегатор земельных аукционов России",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lots.router, prefix="/api/lots", tags=["lots"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(telegram.router, prefix="/api/telegram", tags=["telegram"])


@app.get("/health")
async def health():
    return {"status": "ok"}
