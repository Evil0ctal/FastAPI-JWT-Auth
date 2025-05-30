import logging
import sys
from pathlib import Path
from typing import Optional
from loguru import logger
from pydantic import BaseModel

from app.core.config import settings


class LogConfig(BaseModel):
    """Logging configuration"""
    LOGGER_NAME: str = "fastapi_jwt_auth"
    LOG_FORMAT: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"
    LOG_LEVEL: str = "DEBUG" if settings.ENVIRONMENT == "development" else "INFO"
    
    # File logging
    LOG_TO_FILE: bool = True
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_FILE_ROTATION: str = "20 MB"
    LOG_FILE_RETENTION: str = "1 month"
    
    # JSON logging for production
    JSON_LOGS: bool = settings.ENVIRONMENT == "production"
    
    # Backtrace and diagnose
    BACKTRACE: bool = True
    DIAGNOSE: bool = settings.ENVIRONMENT == "development"


log_config = LogConfig()


def setup_logging():
    """Configure loguru logger"""
    # Remove default logger
    logger.remove()
    
    # Console logging
    if not log_config.JSON_LOGS:
        logger.add(
            sys.stderr,
            format=log_config.LOG_FORMAT,
            level=log_config.LOG_LEVEL,
            backtrace=log_config.BACKTRACE,
            diagnose=log_config.DIAGNOSE,
            colorize=True
        )
    else:
        # JSON format for production
        logger.add(
            sys.stderr,
            format="{message}",
            level=log_config.LOG_LEVEL,
            backtrace=log_config.BACKTRACE,
            diagnose=log_config.DIAGNOSE,
            serialize=True
        )
    
    # File logging
    if log_config.LOG_TO_FILE:
        log_dir = Path(log_config.LOG_FILE_PATH).parent
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            log_config.LOG_FILE_PATH,
            format=log_config.LOG_FORMAT,
            level=log_config.LOG_LEVEL,
            rotation=log_config.LOG_FILE_ROTATION,
            retention=log_config.LOG_FILE_RETENTION,
            backtrace=log_config.BACKTRACE,
            diagnose=log_config.DIAGNOSE,
            serialize=log_config.JSON_LOGS
        )
    
    # Add context to all logs
    logger.configure(
        extra={
            "app_name": settings.PROJECT_NAME,
            "environment": settings.ENVIRONMENT,
            "mode": settings.APP_MODE
        }
    )
    
    return logger


# Intercept standard logging
class InterceptHandler(logging.Handler):
    """Intercept standard logging messages and redirect to loguru"""
    
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_uvicorn_logging():
    """Configure uvicorn to use loguru"""
    # Intercept uvicorn logs
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.error").handlers = [InterceptHandler()]
    
    # Set SQLAlchemy logging
    logging.getLogger("sqlalchemy").handlers = [InterceptHandler()]
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


# Request ID context
from contextvars import ContextVar
from uuid import uuid4

request_id_context: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> str:
    """Get or create request ID"""
    request_id = request_id_context.get()
    if not request_id:
        request_id = str(uuid4())
        request_id_context.set(request_id)
    return request_id


# Configure logger on import
app_logger = setup_logging()