"""BaseAgent — общий каркас для всех продукт-агентов.

Каждый агент наследует BaseAgent и реализует execute(). BaseAgent сам:
- создаёт строку в agent_runs со статусом running;
- ловит исключения → status=failed + текст ошибки;
- по результату execute() ставит done или waiting_approval;
- проставляет finished_at.

Так каждый запуск любого агента логируется единообразно и виден в /admin.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.agent_run import AgentRun


class BaseAgent:
    # Машинное имя агента — переопределить в наследнике.
    name: str = "base"

    async def execute(self, db: AsyncSession) -> tuple[dict[str, Any], bool]:
        """Основная работа агента.

        Возвращает (output_dict, requires_approval).
        output_dict — что записать в agent_runs.output.
        requires_approval — True если результат нужно одобрить вручную.
        """
        raise NotImplementedError

    async def run(self, db: AsyncSession) -> AgentRun:
        """Запускает агента, логирует результат в agent_runs."""
        run = AgentRun(agent_name=self.name, status="running")
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            output, requires_approval = await self.execute(db)
            run.output = output
            run.requires_approval = requires_approval
            run.status = "waiting_approval" if requires_approval else "done"
        except Exception as e:
            run.status = "failed"
            run.error = f"{type(e).__name__}: {e}"
            print(f"[agent:{self.name}] failed: {run.error}")

        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(run)
        return run
