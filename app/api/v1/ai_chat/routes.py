from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import ai_tool_context
from app.ai.streaming import stream_chat
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/v1/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
async def chat(
    req: ChatRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    compiled = request.app.state.chat_graph

    async def gen():
        async with ai_tool_context(session):
            async for chunk in stream_chat(
                message=req.message,
                session_id=req.session_id,
                compiled_graph=compiled,
            ):
                yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
