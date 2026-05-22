"""API продукт-агентов — для страницы /admin → Агенты.

  · GET  /api/agents/runs              — журнал запусков
  · POST /api/agents/{name}/trigger    — запустить агента вручную
  · POST /api/agents/runs/{id}/publish — одобрить и опубликовать черновик
  · POST /api/agents/runs/{id}/skip    — отклонить черновик
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.user import User
from models.agent_run import AgentRun
from api.users import get_current_user

router = APIRouter()


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ только для администратора")
    return user


# Реестр агентов: имя → (человекочитаемое название, async-фабрика агента)
def _agent_registry():
    from services.agents.tg_lot_of_the_day import TgLotOfTheDayAgent
    from services.agents.morning_check import MorningCheckAgent
    return {
        "tg_lot_of_the_day": ("Лот дня в @torgi_zemli", TgLotOfTheDayAgent),
        "morning_check": ("Утренний health-check", MorningCheckAgent),
    }


@router.get("/runs")
async def list_runs(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Последние 50 запусков всех агентов."""
    rows = (await db.execute(
        select(AgentRun).order_by(desc(AgentRun.id)).limit(50)
    )).scalars().all()
    registry = _agent_registry()
    return {
        "agents": [
            {"name": name, "title": title}
            for name, (title, _cls) in registry.items()
        ],
        "runs": [
            {
                "id": r.id,
                "agent_name": r.agent_name,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "output": r.output,
                "requires_approval": r.requires_approval,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                "error": r.error,
            }
            for r in rows
        ],
    }


@router.post("/{agent_name}/trigger")
async def trigger_agent(
    agent_name: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Запустить агента вручную прямо сейчас (не дожидаясь расписания)."""
    registry = _agent_registry()
    if agent_name not in registry:
        raise HTTPException(status_code=404, detail="Агент не найден")
    _title, agent_cls = registry[agent_name]
    run = await agent_cls().run(db)
    return {
        "id": run.id,
        "status": run.status,
        "output": run.output,
        "error": run.error,
    }


@router.post("/runs/{run_id}/publish")
async def publish_run(
    run_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Одобрить черновик и опубликовать в TG-канал."""
    run = (await db.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Запуск не найден")
    if run.status != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"Нельзя опубликовать запуск в статусе «{run.status}»")

    output = run.output or {}
    post_text = output.get("post_text")
    if not post_text:
        raise HTTPException(status_code=400, detail="В черновике нет текста поста")

    if run.agent_name == "tg_lot_of_the_day":
        from services.agents.tg_lot_of_the_day import publish_to_channel
        try:
            await publish_to_channel(post_text, output.get("channel", "@torgi_zemli"))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Ошибка публикации в Telegram: {e}")
    else:
        raise HTTPException(status_code=400, detail="Публикация не поддерживается для этого агента")

    run.status = "published"
    run.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": run.id, "status": run.status}


@router.post("/runs/{run_id}/skip")
async def skip_run(
    run_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Отклонить черновик — пост не публикуется."""
    run = (await db.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Запуск не найден")
    if run.status != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"Нельзя отклонить запуск в статусе «{run.status}»")
    run.status = "skipped"
    await db.commit()
    return {"id": run.id, "status": run.status}
