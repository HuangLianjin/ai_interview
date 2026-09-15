"""人机协同 API：用户申诉 + 管理员复核 + 审计日志。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.auth import require_auth
from app.services import human_review_service

router = APIRouter(prefix="/api/appeals", tags=["评分申诉"])
admin_router = APIRouter(prefix="/api/admin", tags=["管理员复核"])


def _user_id(payload: dict) -> str:
    return str(payload.get("sub", "default_user"))


async def require_admin(payload: dict = Depends(require_auth)) -> dict:
    if not await human_review_service.is_admin(_user_id(payload)):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload


class AppealCreate(BaseModel):
    session_id: str
    question_index: int = Field(..., ge=0)
    reason: str = Field(..., min_length=2, max_length=1000)


class AppealDecision(BaseModel):
    revised_total: Optional[float] = Field(None, ge=0, le=10)
    admin_note: Optional[str] = Field(None, max_length=1000)
    status: str = Field("resolved", pattern="^(resolved|rejected)$")


@router.post("")
async def create_appeal(request: AppealCreate, payload: dict = Depends(require_auth)):
    """用户对某题评分发起申诉。"""
    appeal_id = await human_review_service.create_appeal(
        user_id=_user_id(payload),
        session_id=request.session_id,
        question_index=request.question_index,
        reason=request.reason,
    )
    return {"success": True, "appeal_id": appeal_id}


@router.get("/mine")
async def my_appeals(
    limit: int = Query(50, ge=1, le=200),
    payload: dict = Depends(require_auth),
):
    """查看自己的申诉记录和处理结果。"""
    appeals = await human_review_service.list_my_appeals(_user_id(payload), limit=limit)
    return {"success": True, "appeals": appeals}


@admin_router.get("/appeals")
async def admin_list_appeals(
    status: Optional[str] = Query("pending"),
    limit: int = Query(100, ge=1, le=500),
    payload: dict = Depends(require_admin),
):
    """管理员查看待处理申诉。"""
    appeals = await human_review_service.list_appeals(status=status, limit=limit)
    return {"success": True, "appeals": appeals}


@admin_router.post("/appeals/{appeal_id}/decide")
async def admin_decide_appeal(
    appeal_id: int,
    request: AppealDecision,
    payload: dict = Depends(require_admin),
):
    """管理员复核评分：可改分并记录备注，操作写入审计日志。"""
    ok = await human_review_service.decide_appeal(
        admin_id=_user_id(payload),
        appeal_id=appeal_id,
        revised_total=request.revised_total,
        admin_note=request.admin_note,
        status=request.status,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="申诉不存在")
    return {"success": True}


@admin_router.get("/audit-logs")
async def admin_audit_logs(
    limit: int = Query(200, ge=1, le=500),
    payload: dict = Depends(require_admin),
):
    """查看人工操作审计日志。"""
    logs = await human_review_service.list_audit_logs(limit=limit)
    return {"success": True, "logs": logs}
