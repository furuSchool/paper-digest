from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from schemas import GoogleTokenStatus
from services import auth_service
import os

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def google_auth() -> RedirectResponse:
    """Google OAuth2 認証フローを開始する。"""
    auth_url, _ = auth_service.get_auth_url()
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """OAuth2コールバック。トークンを保存してフロントへリダイレクト。"""
    await auth_service.exchange_code(code, db)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/settings?auth=success")


@router.get("/status", response_model=GoogleTokenStatus)
async def auth_status(db: AsyncSession = Depends(get_db)) -> GoogleTokenStatus:
    creds = await auth_service.get_credentials(db)
    if creds:
        from models import GoogleToken
        from sqlalchemy import select

        result = await db.execute(select(GoogleToken))
        token = result.scalars().first()
        return GoogleTokenStatus(
            authenticated=True, token_expiry=token.token_expiry if token else None
        )
    return GoogleTokenStatus(authenticated=False)


@router.delete("/google", status_code=204)
async def reset_auth(db: AsyncSession = Depends(get_db)) -> None:
    await auth_service.delete_credentials(db)
