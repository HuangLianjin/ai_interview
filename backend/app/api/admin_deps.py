"""管理员权限依赖。"""

from fastapi import Depends, HTTPException

from app.api.auth import require_auth
from app.services import human_review_service


def _user_id(payload: dict) -> str:
    return str(payload.get("sub", "default_user"))


async def require_admin(payload: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备管理员角色。"""
    if not await human_review_service.is_admin(_user_id(payload)):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload
