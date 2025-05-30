from typing import Optional, Literal
from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI JWT Auth Template"
    PROJECT_VERSION: str = "1.0.0"
    
    # Application Mode
    APP_MODE: Literal["demo", "production"] = Field(default="demo", env="APP_MODE")
    
    # JWT Settings
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Rate Limiting Settings
    RATE_LIMIT_ENABLED: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_REQUESTS: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    
    # Email Settings
    SMTP_HOST: str = Field(default="localhost", env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: str = Field(default="", env="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", env="SMTP_PASSWORD")
    SMTP_FROM: str = Field(default="noreply@example.com", env="SMTP_FROM")
    SMTP_TLS: bool = Field(default=True, env="SMTP_TLS")
    SMTP_SSL: bool = Field(default=False, env="SMTP_SSL")
    EMAIL_ENABLED: bool = Field(default=False, env="EMAIL_ENABLED")
    
    # Frontend URL for email links
    FRONTEND_URL: str = Field(default="http://localhost:8000", env="FRONTEND_URL")
    
    # OAuth Settings
    GOOGLE_CLIENT_ID: str = Field(default="", env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", env="GOOGLE_CLIENT_SECRET")
    GITHUB_CLIENT_ID: str = Field(default="", env="GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: str = Field(default="", env="GITHUB_CLIENT_SECRET")
    
    # Database Settings
    DATABASE_TYPE: Literal["sqlite", "mysql"] = Field(default="sqlite", env="DATABASE_TYPE")
    
    # SQLite Settings
    SQLITE_URL: str = Field(default="sqlite+aiosqlite:///./demo.db", env="SQLITE_URL")
    
    # MySQL Settings
    MYSQL_HOST: str = Field(default="localhost", env="MYSQL_HOST")
    MYSQL_PORT: int = Field(default=3306, env="MYSQL_PORT")
    MYSQL_USER: str = Field(default="root", env="MYSQL_USER")
    MYSQL_PASSWORD: str = Field(default="password", env="MYSQL_PASSWORD")
    MYSQL_DATABASE: str = Field(default="fastapi_jwt_db", env="MYSQL_DATABASE")
    
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_TYPE == "sqlite":
            return self.SQLITE_URL
        else:
            return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    @computed_field
    @property
    def IS_DEMO_MODE(self) -> bool:
        return self.APP_MODE == "demo"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

