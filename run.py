import uvicorn
import socket
from app.core.config import settings
from app.core.logging import app_logger as logger

if __name__ == "__main__":
    logger.info(f"Starting {settings.PROJECT_NAME} server...")
    
    # Try to use port 8000, fallback to 8001 if in use
    port = 8000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('', port))
        sock.close()
    except OSError:
        port = 8001
        logger.info(f"Port 8000 is in use, using port {port} instead")
    
    # Uvicorn configuration
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.ENVIRONMENT == "development",
        log_config=None,  # Use our custom logging
        access_log=True,
        use_colors=True
    )
