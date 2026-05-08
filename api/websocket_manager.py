from fastapi import WebSocket
from api.models import AgentEvent

class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, pipeline_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(pipeline_id, []).append(websocket)

    def disconnect(self, pipeline_id: str, websocket: WebSocket):
        if pipeline_id in self.connections:
            try:
                self.connections[pipeline_id].remove(websocket)
            except ValueError:
                pass

    async def broadcast(self, pipeline_id: str, event: AgentEvent):
        conns = list(self.connections.get(pipeline_id, []))
        dead = []
        for ws in conns:
            try:
                await ws.send_text(event.model_dump_json())
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(pipeline_id, ws)
