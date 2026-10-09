from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import chat_turn

app = FastAPI(title="Taquería El Fogón - agente")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# One conversation history per browser session, kept in memory (lost when the server restarts)
sessions = {}

# Cap on a single message, so nobody can send the model a huge text
MAX_MESSAGE_CHARS = 1000


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.post("/chat")
def chat(req: ChatRequest):
    # Plain def, not async: FastAPI runs it in a worker thread, so a slow model call
    # doesn't block other customers
    text = req.message.strip()[:MAX_MESSAGE_CHARS]
    if not text:
        return {"reply": ""}
    history = sessions.setdefault(req.session_id, [])
    history.append({"role": "user", "content": text})
    return {"reply": chat_turn(history, session_id=req.session_id)}