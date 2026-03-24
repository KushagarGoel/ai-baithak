"""FastAPI application for Agent Council backend."""

import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import router as api_router
from app.api.websocket import handle_websocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


app = FastAPI(
    title=settings.APP_NAME,
    description="MCP-powered Agent Council API",
    version="0.1.0",
    debug=settings.DEBUG,
)

# CORS middleware - expanded for WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # More permissive for WebSocket connections
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.websocket("/ws/discussion/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time discussion updates."""
    # Log connection attempt for debugging
    print(f"[WebSocket] Connection attempt: {session_id} from {websocket.client}")

    # Accept the WebSocket connection first
    await websocket.accept()

    # Disable Starlette's automatic keepalive ping to prevent timeouts
    # We use our own application-level ping/pong
    websocket.ping_interval = None
    websocket.ping_timeout = None

    try:
        await handle_websocket(websocket, session_id)
    except Exception as e:
        print(f"[WebSocket] Fatal error in endpoint for {session_id}: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "agent-council-api"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "description": "MCP-powered Agent Council API",
        "endpoints": {
            "api": "/api",
            "websocket": "/ws/discussion/{session_id}",
            "health": "/health",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
