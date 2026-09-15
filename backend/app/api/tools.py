"""Agent 工具列表与调用 API（Function Calling 风格的本地工具层）。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import require_auth
from app.services import tools_service

router = APIRouter(prefix="/api/tools", tags=["Agent 工具"])


class ToolInvokeRequest(BaseModel):
    params: dict = Field(default_factory=dict)
    session_id: Optional[str] = None


@router.get("")
async def list_tools(payload: dict = Depends(require_auth)):
    """列出可用工具及参数 schema，可直接用于 Function Calling 或 MCP 注册。"""
    return {"success": True, "tools": tools_service.list_tools()}


@router.post("/{name}/invoke")
async def invoke_tool(
    name: str,
    request: ToolInvokeRequest,
    payload: dict = Depends(require_auth),
):
    """调用指定工具，调用过程会写入全链路 Trace。"""
    result = await tools_service.invoke_tool(
        name=name,
        params=request.params,
        session_id=request.session_id,
    )
    if not result.get("success") and result.get("error", "").startswith("未知工具"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result
