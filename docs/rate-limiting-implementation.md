# API Rate Limiting Implementation

## Overview

API rate limiting has been implemented to protect the FastAPI JWT Auth Template from abuse and ensure fair usage. The implementation uses an in-memory store by default, with the option to upgrade to Redis for production deployments.

## Features

- **Flexible Configuration**: Configure rate limits via environment variables
- **Per-IP Limiting**: Tracks requests by client IP address
- **Path-Specific Rules**: Apply different limits to different endpoints
- **Route-Level Control**: Add custom rate limits to specific routes
- **429 Status Codes**: Proper HTTP status codes with retry information
- **Automatic Cleanup**: Background task removes old entries

## Implementation Details

### Components

1. **Rate Limit Store** (`app/core/rate_limit.py`)
   - In-memory storage using Python dictionaries
   - Async-safe with locks
   - Automatic cleanup of old entries
   - Can be replaced with Redis for production

2. **Middleware**
   - Global rate limiting for all API endpoints
   - Configurable paths and exclusions
   - Adds rate limit headers to responses

3. **Route Dependency**
   - Fine-grained control for specific endpoints
   - Custom limits per route

### Configuration

Add to your `.env` file:

```env
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60  # seconds
```

### Usage Examples

#### Global Rate Limiting
All API endpoints are protected by default:
- 100 requests per 60 seconds per IP
- Excludes login and register endpoints

#### Route-Specific Rate Limiting
```python
from app.core.rate_limit import rate_limit

@router.post("/login", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))])
async def login(...):
    # Max 5 login attempts per minute
```

#### Response Headers
When rate limited, the API returns:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Window: 60
X-RateLimit-Remaining: 0

{
  "detail": "Rate limit exceeded",
  "retry_after": 30
}
```

## Security Considerations

1. **Login Protection**: Strict limits on login attempts (5 per minute)
2. **Registration Protection**: Prevents spam registrations (3 per 5 minutes)
3. **API Protection**: General protection for all API endpoints

## Production Considerations

For production deployments, consider:
1. Using Redis instead of in-memory storage
2. Implementing user-based rate limiting (not just IP-based)
3. Adding rate limit bypass for authenticated admins
4. Monitoring rate limit hits for security analysis

## Testing

Test rate limiting with curl:
```bash
# Test login rate limit (will be blocked after 5 requests)
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"test"}'
  echo
done
```

## Next Steps

- Implement Redis backend for distributed systems
- Add user-based rate limiting
- Create rate limit monitoring dashboard
- Add WebSocket rate limiting