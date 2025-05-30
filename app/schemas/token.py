from typing import Optional
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenRevoke(BaseModel):
    refresh_token: str