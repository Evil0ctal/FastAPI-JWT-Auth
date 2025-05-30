"""
OAuth endpoints for social login
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse

from app.db.database import get_db
from app.services.oauth import oauth_service
from app.core.config import settings

router = APIRouter()


@router.get("/providers")
async def get_oauth_providers():
    """Get available OAuth providers"""
    providers = []
    if hasattr(settings, 'GOOGLE_CLIENT_ID') and settings.GOOGLE_CLIENT_ID:
        providers.append({
            "name": "google",
            "display_name": "Google",
            "icon": "google"
        })
    if hasattr(settings, 'GITHUB_CLIENT_ID') and settings.GITHUB_CLIENT_ID:
        providers.append({
            "name": "github", 
            "display_name": "GitHub",
            "icon": "github"
        })
    return {"providers": providers}


@router.get("/authorize/{provider}")
async def oauth_authorize(provider: str):
    """Redirect to OAuth provider for authorization"""
    auth_url = await oauth_service.get_authorization_url(provider)
    if not auth_url:
        raise HTTPException(status_code=404, detail=f"OAuth provider '{provider}' not found")
    
    return RedirectResponse(url=auth_url)


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback from provider"""
    result = await oauth_service.handle_callback(db, provider, code, state)
    
    if not result:
        # Redirect to login page with error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/static/login.html?oauth_error=authentication_failed"
        )
    
    # Redirect to dashboard with token
    # In production, you might want to use a more secure method
    # like setting a secure HTTP-only cookie
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/static/dashboard.html?token={result['access_token']}"
    )