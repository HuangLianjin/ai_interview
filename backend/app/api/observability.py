"""全链路可观测性、用户反馈与效果指标 API。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.admin_deps import require_admin
from app.api.auth import require_auth
from app.services import trace_service

router = APIRouter(prefix="/api/observability", tags=["可观测性"])
feedback_router = APIRouter(prefix="/api/feedback", tags=["用户反馈"])


def _user_id(payload: dict) -> str:
    return str(payload.get("sub", "default_user"))


class FeedbackRequest(BaseModel):
    target_type: str = Field(..., description="interview / report / resume / trip")
    target_id: Optional[str] = None
    session_id: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[list[str]] = None
    comment: Optional[str] = None


@router.get("/runs")
async def get_runs(
    session_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    payload: dict = Depends(require_admin),
):
    """查看运行记录；传 session_id 看某次面试，不传看最近记录。"""
    runs = await trace_service.list_runs(session_id=session_id, limit=limit)
    return {"success": True, "runs": runs}


@router.get("/runs/{run_id}")
async def get_run_detail(run_id: str, payload: dict = Depends(require_admin)):
    """查看某次运行的完整节点链路、耗时、Token 和错误。"""
    detail = await trace_service.get_run_detail(run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return {"success": True, "run": detail}


@router.get("/summary")
async def get_summary(
    days: int = Query(7, ge=1, le=90),
    payload: dict = Depends(require_admin),
):
    """成功率、平均/P95 延迟、Token 消耗、节点耗时统计。"""
    summary = await trace_service.get_trace_summary(days=days)
    return {"success": True, "summary": summary}


@router.get("/product-metrics")
async def get_product_metrics(
    days: int = Query(7, ge=1, le=90),
    payload: dict = Depends(require_admin),
):
    """真实使用与效果指标：完成率、反馈评分、产出量、待修复评测失败数。"""
    metrics = await trace_service.get_product_metrics(days=days)
    return {"success": True, "metrics": metrics}


@router.get("/eval-failures")
async def get_eval_failures(
    status: Optional[str] = Query("open"),
    limit: int = Query(200, ge=1, le=500),
    payload: dict = Depends(require_admin),
):
    """查看评测失败样本池，用于反哺优化。"""
    failures = await trace_service.list_eval_failures(status=status, limit=limit)
    return {"success": True, "failures": failures}


@router.post("/eval-failures/{failure_id}/resolve")
async def resolve_eval_failure(
    failure_id: int,
    payload: dict = Depends(require_admin),
):
    """把评测失败样本标记为已解决。"""
    ok = await trace_service.resolve_eval_failure(failure_id)
    if not ok:
        raise HTTPException(status_code=404, detail="失败样本不存在")
    return {"success": True}


@feedback_router.post("")
async def submit_feedback(
    request: FeedbackRequest,
    payload: dict = Depends(require_auth),
):
    """提交用户真实感受评价（1-5 星 + 标签 + 评论）。"""
    feedback_id = await trace_service.save_feedback(
        user_id=_user_id(payload),
        target_type=request.target_type,
        target_id=request.target_id,
        session_id=request.session_id,
        rating=request.rating,
        tags=request.tags,
        comment=request.comment,
    )
    return {"success": True, "feedback_id": feedback_id}


@feedback_router.get("")
async def my_feedback(
    target_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    payload: dict = Depends(require_auth),
):
    """查看当前用户提交过的反馈。"""
    items = await trace_service.list_feedback(
        user_id=_user_id(payload),
        target_type=target_type,
        limit=limit,
    )
    return {"success": True, "feedback": items}
