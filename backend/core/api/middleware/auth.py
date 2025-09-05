# backend/middleware/auth.py
from fastapi import Request, HTTPException

def validate_api_key(request: Request, key_name: str, expected: str):
    token = request.headers.get("x-api-key")
    if token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
