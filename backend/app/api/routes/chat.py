from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatNotConfiguredError, chat_reply
from app.services.languages import assert_supported_language


router = APIRouter()


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, _user=Depends(get_current_user)) -> ChatResponse:
    try:
        lang = assert_supported_language(payload.language)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language") from e

    try:
        assistant_text = chat_reply(lang, payload.user_text)
    except ChatNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat failed") from e

    return ChatResponse(assistant_text=assistant_text)

