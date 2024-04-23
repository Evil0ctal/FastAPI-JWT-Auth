from fastapi import FastAPI, Depends, HTTPException
from auth import get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

from db import get_user_by_email

app = FastAPI(docs_url='/')


@app.post("/token")
async def login_for_access_token(email: str):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"email": user['email'], "create_time": user['create_time'], "scopes": user['scopes'], "evil1": "evil1"},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/protected-route")
def protected_route(user=Depends(get_current_user)):
    return {"message": "Access to protected route granted", "user": user}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=80)
