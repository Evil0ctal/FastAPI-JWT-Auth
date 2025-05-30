"""
OAuth Service for social login integration
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import httpx
import secrets
import json

from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.services.user import create_user_oauth
from app.core.config import settings
from app.core.security import create_access_token
from app.core.logging import app_logger as logger


class OAuthProvider:
    """Base OAuth provider class"""
    
    def __init__(self, name: str, client_id: str, client_secret: str, redirect_uri: str):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    async def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL"""
        raise NotImplementedError
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        raise NotImplementedError
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user info from OAuth provider"""
        raise NotImplementedError


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth provider"""
    
    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    async def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"{self.AUTHORIZATION_URL}?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            return {
                "provider_user_id": data["id"],
                "email": data["email"],
                "full_name": data.get("name"),
                "avatar_url": data.get("picture"),
                "is_verified": data.get("verified_email", False)
            }


class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth provider"""
    
    AUTHORIZATION_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_INFO_URL = "https://api.github.com/user"
    
    async def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
            "state": state
        }
        return f"{self.AUTHORIZATION_URL}?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri
                },
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            # Get user info
            response = await client.get(
                self.USER_INFO_URL,
                headers={"Authorization": f"token {access_token}"}
            )
            response.raise_for_status()
            user_data = response.json()
            
            # Get primary email
            email_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}"}
            )
            email_response.raise_for_status()
            emails = email_response.json()
            primary_email = next((e["email"] for e in emails if e["primary"]), None)
            
            return {
                "provider_user_id": str(user_data["id"]),
                "email": primary_email or user_data.get("email"),
                "full_name": user_data.get("name"),
                "avatar_url": user_data.get("avatar_url"),
                "is_verified": True  # GitHub emails are pre-verified
            }


class OAuthService:
    """OAuth service for managing social logins"""
    
    def __init__(self):
        self.providers = {}
        self._init_providers()
    
    def _init_providers(self):
        """Initialize OAuth providers"""
        # Google OAuth
        if hasattr(settings, 'GOOGLE_CLIENT_ID') and settings.GOOGLE_CLIENT_ID:
            self.providers["google"] = GoogleOAuthProvider(
                name="google",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                redirect_uri=f"{settings.FRONTEND_URL}/auth/callback/google"
            )
        
        # GitHub OAuth
        if hasattr(settings, 'GITHUB_CLIENT_ID') and settings.GITHUB_CLIENT_ID:
            self.providers["github"] = GitHubOAuthProvider(
                name="github",
                client_id=settings.GITHUB_CLIENT_ID,
                client_secret=settings.GITHUB_CLIENT_SECRET,
                redirect_uri=f"{settings.FRONTEND_URL}/auth/callback/github"
            )
    
    def get_provider(self, provider_name: str) -> Optional[OAuthProvider]:
        """Get OAuth provider by name"""
        return self.providers.get(provider_name)
    
    async def get_authorization_url(self, provider_name: str) -> Optional[str]:
        """Get OAuth authorization URL"""
        provider = self.get_provider(provider_name)
        if not provider:
            return None
        
        state = secrets.token_urlsafe(32)
        # TODO: Store state in cache/database for validation
        return await provider.get_authorization_url(state)
    
    async def handle_callback(
        self, 
        db: AsyncSession, 
        provider_name: str, 
        code: str,
        state: str
    ) -> Optional[Dict[str, Any]]:
        """Handle OAuth callback"""
        provider = self.get_provider(provider_name)
        if not provider:
            return None
        
        # TODO: Validate state token
        
        try:
            # Exchange code for token
            token_data = await provider.exchange_code_for_token(code)
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            
            if not access_token:
                logger.error(f"No access token in response from {provider_name}")
                return None
            
            # Get user info
            user_info = await provider.get_user_info(access_token)
            
            # Check if OAuth account exists
            oauth_account = await self.get_oauth_account(
                db, 
                provider_name, 
                user_info["provider_user_id"]
            )
            
            if oauth_account:
                # Update tokens
                oauth_account.access_token = access_token
                if refresh_token:
                    oauth_account.refresh_token = refresh_token
                if expires_in:
                    oauth_account.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                oauth_account.updated_at = datetime.utcnow()
                
                await db.commit()
                user = oauth_account.user
            else:
                # Check if user with email exists
                user = await self.get_user_by_email(db, user_info["email"])
                
                if user:
                    # Link OAuth account to existing user
                    await self.create_oauth_account(
                        db,
                        user_id=user.id,
                        provider=provider_name,
                        provider_user_id=user_info["provider_user_id"],
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_in=expires_in
                    )
                else:
                    # Create new user
                    user = await create_user_oauth(
                        db,
                        email=user_info["email"],
                        full_name=user_info.get("full_name"),
                        avatar_url=user_info.get("avatar_url"),
                        is_verified=user_info.get("is_verified", False)
                    )
                    
                    # Create OAuth account
                    await self.create_oauth_account(
                        db,
                        user_id=user.id,
                        provider=provider_name,
                        provider_user_id=user_info["provider_user_id"],
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_in=expires_in
                    )
            
            # Create JWT token
            jwt_token = create_access_token({"sub": str(user.id)})
            
            return {
                "access_token": jwt_token,
                "token_type": "bearer",
                "user": user
            }
            
        except Exception as e:
            logger.error(f"OAuth callback error for {provider_name}: {str(e)}")
            return None
    
    async def get_oauth_account(
        self, 
        db: AsyncSession, 
        provider: str, 
        provider_user_id: str
    ) -> Optional[OAuthAccount]:
        """Get OAuth account by provider and provider user ID"""
        query = select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id
        ).options(
            # Eager load user relationship
            selectinload(OAuthAccount.user)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email"""
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_oauth_account(
        self,
        db: AsyncSession,
        user_id: int,
        provider: str,
        provider_user_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None
    ) -> OAuthAccount:
        """Create OAuth account"""
        oauth_account = OAuthAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        )
        db.add(oauth_account)
        await db.commit()
        await db.refresh(oauth_account)
        return oauth_account


# Create global OAuth service instance
oauth_service = OAuthService()


__all__ = ["oauth_service", "OAuthService"]
