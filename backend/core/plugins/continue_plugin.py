from fastapi import APIRouter, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from backend.core import state_manager
import asyncio, time
import json
import uuid

router = APIRouter()
websocket_clients = set()

def register(app):
    app.include_router(router)

@router.get("/agent/status")
def agent_status():
    return {"status": "online"}

@router.post("/agent/invoke")
async def agent_invoke(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    session_id = body.get("session_id", "default")
    instruction = body.get("instruction", "")

    # Save initial state
    state_manager.add_session(session_id, {
        "last_instruction": instruction,
        "task_status": "queued"
    })

    # Queue background task
    background_tasks.add_task(handle_task, session_id, instruction)
    return JSONResponse({
        "session_id": session_id,
        "status": "queued"
    })

def handle_task(session_id, instruction):
    state = state_manager.load_state()
    state["sessions"][session_id]["task_status"] = "running"
    state_manager.save_state(state)
    time.sleep(2)
    result = f"Task completed: {instruction}"
    state["sessions"][session_id]["task_result"] = result
    state["sessions"][session_id]["task_status"] = "done"
    state_manager.save_state(state)
    asyncio.run(notify_clients(session_id, result))

async def notify_clients(session_id, result):
    dead_clients = []
    for ws in websocket_clients:
        try:
            await ws.send_json({"session_id": session_id, "result": result})
        except:
            dead_clients.append(ws)
    for ws in dead_clients:
        websocket_clients.remove(ws)

@router.websocket("/agent/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)

@router.get("/agent/task/{session_id}")
def task_status(session_id: str):
    state = state_manager.load_state()
    session = state["sessions"].get(session_id, {})
    return {
        "status": session.get("task_status", "unknown"),
        "result": session.get("task_result")
    }

@router.post("/chat")
async def chat(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "default")
    message = body.get("message", "")
    state = state_manager.load_state()
    session = state["sessions"].setdefault(session_id, {"chat": []})
    session["chat"].append({"user": message})
    state_manager.save_state(state)

    async def sse():
        reply = f"Echo: {message}"
        partial = ""
        for char in reply:
            partial += char
            yield f"data: {partial}\n\n"
            await asyncio.sleep(0.03)
        session["chat"][-1]["echo"] = reply
        state_manager.save_state(state)

    return StreamingResponse(sse(), media_type="text/event-stream")

# OpenAI-compatible endpoints for Continue extension
@router.post("/v1/chat/completions")
async def openai_chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "echo-001")
    stream = body.get("stream", True)

    # Extract the last user message
    user_message = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            user_message = message.get("content", "")
            break

    if not user_message:
        return JSONResponse({
            "error": "No user message found"
        }, status_code=400)

    # Generate response
    response_text = f"Echo-001 Response: {user_message}"

    if stream:
        async def stream_response():
            # Send initial chunk
            yield f"data: {json.dumps({'id': str(uuid.uuid4()), 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}, 'finish_reason': None}]})}\n\n"

            # Stream the response character by character
            for char in response_text:
                yield f"data: {json.dumps({'id': str(uuid.uuid4()), 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'content': char}, 'finish_reason': None}]})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for streaming effect

            # Send final chunk
            yield f"data: {json.dumps({'id': str(uuid.uuid4()), 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")
    else:
        return JSONResponse({
            "id": str(uuid.uuid4()),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(user_message.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(user_message.split()) + len(response_text.split())
            }
        })

@router.get("/v1/models")
async def openai_models():
    return JSONResponse({
        "object": "list",
        "data": [
            {
                "id": "echo-001",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "echo-devcon"
            }
        ]
    })
