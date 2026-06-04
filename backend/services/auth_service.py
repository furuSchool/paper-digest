import os
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import GoogleToken

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]

# 認証フロー中の Flow オブジェクトを保持（PKCE の code_verifier を引き継ぐため）
_pending_flow: Flow | None = None


def _client_config() -> dict:
    return {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")],
        }
    }


def get_auth_url() -> tuple[str, str]:
    """OAuth2認証URLと state を返す。"""
    global _pending_flow
    _pending_flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    _pending_flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    auth_url, state = _pending_flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


async def exchange_code(code: str, db: AsyncSession) -> None:
    """認証コードをトークンと交換してDBに保存する。"""
    global _pending_flow
    if _pending_flow is None:
        raise RuntimeError("認証フローが開始されていません。/auth/google から再度やり直してください。")
    flow = _pending_flow
    _pending_flow = None
    flow.fetch_token(code=code)

    creds = flow.credentials
    expiry = creds.expiry or datetime.now(timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    result = await db.execute(select(GoogleToken))
    token = result.scalars().first()

    if token:
        token.access_token = creds.token
        token.refresh_token = creds.refresh_token or token.refresh_token
        token.token_expiry = expiry
        token.updated_at = datetime.now(timezone.utc)
    else:
        token = GoogleToken(
            access_token=creds.token,
            refresh_token=creds.refresh_token or "",
            token_expiry=expiry,
        )
        db.add(token)

    await db.commit()


async def get_credentials(db: AsyncSession) -> Credentials | None:
    """DBからトークンを取得しCredentialsを返す。期限切れは自動refresh。"""
    result = await db.execute(select(GoogleToken))
    token = result.scalars().first()
    if not token:
        return None

    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        import google.auth.transport.requests
        request = google.auth.transport.requests.Request()
        creds.refresh(request)

        token.access_token = creds.token
        token.token_expiry = creds.expiry or datetime.now(timezone.utc)
        if token.token_expiry.tzinfo is None:
            token.token_expiry = token.token_expiry.replace(tzinfo=timezone.utc)
        token.updated_at = datetime.now(timezone.utc)
        await db.commit()

    return creds


async def delete_credentials(db: AsyncSession) -> None:
    """DBのトークンを削除する。"""
    result = await db.execute(select(GoogleToken))
    token = result.scalars().first()
    if token:
        await db.delete(token)
        await db.commit()
