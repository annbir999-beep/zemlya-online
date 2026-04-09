from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from models.user import User
from models.alert import Subscription
from api.users import get_current_user

router = APIRouter()


@router.get("/history")
async def payment_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    subs = result.scalars().all()
    return {
        "items": [
            {
                "id": s.id,
                "plan": s.plan,
                "amount": s.amount,
                "months": s.months,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "paid_at": s.paid_at.isoformat() if s.paid_at else None,
            }
            for s in subs
        ]
    }
