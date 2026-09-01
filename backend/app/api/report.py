"""面评报告与逐题评分接口。"""
import logging

from fastapi import APIRouter, HTTPException

from app.services.report_service import generate_session_report
from app.services.scoring_service import get_session_scores

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["report"])


@router.post("/{session_id}/report")
async def generate_report(session_id: str):
    """生成并返回面评报告（Markdown + PDF）。"""
    try:
        return await generate_session_report(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成面评报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="生成面评报告失败")


@router.get("/{session_id}/scores")
async def session_scores(session_id: str):
    """返回该会话的逐题评分。"""
    scores = await get_session_scores(session_id)
    return {"success": True, "scores": scores}