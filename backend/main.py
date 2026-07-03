from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from db.database import engine, Base
# Импортируем модели чтобы Base.metadata знал о них (для create_all при первом старте)
from models import promo  # noqa: F401
from models import agent_run  # noqa: F401
from models import content  # noqa: F401
from models import lead  # noqa: F401
from api import lots, users, alerts, ai, payments, subscriptions, telegram, admin, agents, blog, leads, seo, services
from core.config import settings
from core.ratelimit import limiter
from core.sentry import init_sentry

init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Торги Земли — API",
    description="Агрегатор земельных аукционов России",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(blog.router, prefix="/api/blog", tags=["blog"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(seo.router, prefix="/api/seo", tags=["seo"])
app.include_router(services.router, prefix="/api/services", tags=["services"])


@app.get("/health")
async def health():
    return {"status": "ok"}
