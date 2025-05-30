from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
import asyncio
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class RateLimitStore:
    """In-memory rate limit store (can be replaced with Redis in production)"""
    
    def __init__(self):
        self._store: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._cleanup_interval = 300  # 5 minutes
        self._cleanup_task = None
    
    async def start_cleanup(self):
        """Start background cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup(self):
        """Stop background cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self):
        """Background task to cleanup old entries"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_old_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in rate limit cleanup: {e}")
    
    async def _cleanup_old_entries(self):
        """Remove entries older than 1 hour"""
        async with self._lock:
            cutoff = datetime.utcnow() - timedelta(hours=1)
            for key in list(self._store.keys()):
                self._store[key] = [
                    timestamp for timestamp in self._store[key]
                    if timestamp > cutoff
                ]
                if not self._store[key]:
                    del self._store[key]
    
    async def is_allowed(
        self, 
        key: str, 
        max_requests: int, 
        window_seconds: int
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed under rate limit
        Returns: (is_allowed, retry_after_seconds)
        """
        async with self._lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=window_seconds)
            
            # Filter out old requests
            self._store[key] = [
                timestamp for timestamp in self._store[key]
                if timestamp > window_start
            ]
            
            # Check if limit exceeded
            if len(self._store[key]) >= max_requests:
                # Calculate retry after
                oldest_request = min(self._store[key])
                retry_after = int((oldest_request + timedelta(seconds=window_seconds) - now).total_seconds())
                return False, max(retry_after, 1)
            
            # Add current request
            self._store[key].append(now)
            return True, None


# Global rate limit store
rate_limit_store = RateLimitStore()


class RateLimiter:
    """Rate limiter middleware"""
    
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        key_func: Optional[callable] = None
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key_func
    
    @staticmethod
    def _default_key_func(request: Request) -> str:
        """Default key function using client IP"""
        client_host = request.client.host if request.client else "unknown"
        return f"rate_limit:{client_host}:{request.url.path}"
    
    async def __call__(self, request: Request) -> Optional[JSONResponse]:
        """Check rate limit for request"""
        key = self.key_func(request)
        is_allowed, retry_after = await rate_limit_store.is_allowed(
            key, self.max_requests, self.window_seconds
        )
        
        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Window": str(self.window_seconds),
                    "X-RateLimit-Remaining": "0"
                }
            )
        
        return None


def create_rate_limit_middleware(
    max_requests: int = 100,
    window_seconds: int = 60,
    paths: Optional[list] = None,
    exclude_paths: Optional[list] = None
):
    """Create rate limit middleware for FastAPI"""
    rate_limiter = RateLimiter(max_requests, window_seconds)
    
    async def rate_limit_middleware(request: Request, call_next):
        # Check if path should be rate limited
        path = request.url.path
        
        if paths and not any(path.startswith(p) for p in paths):
            return await call_next(request)
        
        if exclude_paths and any(path.startswith(p) for p in exclude_paths):
            return await call_next(request)
        
        # Check rate limit
        response = await rate_limiter(request)
        if response:
            return response
        
        # Process request
        return await call_next(request)
    
    return rate_limit_middleware


# Dependency for route-specific rate limiting
def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """Dependency to add rate limiting to specific routes"""
    async def _rate_limit(request: Request):
        # Import here to avoid circular imports
        from app.core.config import settings
        
        # Skip rate limiting if disabled
        if not settings.RATE_LIMIT_ENABLED:
            return
            
        key = f"route_limit:{request.client.host if request.client else 'unknown'}:{request.url.path}"
        is_allowed, retry_after = await rate_limit_store.is_allowed(
            key, max_requests, window_seconds
        )
        
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)}
            )
    
    return _rate_limit
