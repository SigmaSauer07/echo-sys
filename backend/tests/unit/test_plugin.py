from fastapi import APIRouter

router = APIRouter()

def register(app):
    app.include_router(router)

@router.get("/test")
def test_endpoint():
    return {"message": "Test plugin loaded successfully"} 