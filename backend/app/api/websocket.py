"""WebSocket handler for real-time discussion updates."""

import json
import asyncio
import logging
import time
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.models.schemas import (
    CouncilConfig,
    DiscussionTurn,
    DiscussionSegment,
    DiscussionSummary,
    OrchestratorState,
)
from app.core.orchestrator import CouncilOrchestrator

logger = logging.getLogger(__name__)


class DiscussionManager:
    """Manages active WebSocket discussions."""

    def __init__(self):
        self.active_discussions: dict[str, CouncilOrchestrator] = {}
        self.connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Track a new WebSocket connection (already accepted)."""
        try:
            self.connections[session_id] = websocket
            logger.info(f"[WebSocket] Connection tracked for session: {session_id}")
        except Exception as e:
            logger.error(f"[WebSocket] Failed to track connection for {session_id}: {e}")
            raise

    def disconnect(self, session_id: str):
        """Remove a WebSocket connection."""
        logger.info(f"[WebSocket] Disconnecting session: {session_id}")
        if session_id in self.connections:
            try:
                # Signal orchestrator to stop
                self.stop_discussion(session_id)
            except Exception as e:
                logger.error(f"[WebSocket] Error during disconnect cleanup: {e}")
            finally:
                del self.connections[session_id]

    def stop_discussion(self, session_id: str):
        """Signal orchestrator to stop a discussion."""
        if session_id in self.active_discussions:
            orchestrator = self.active_discussions[session_id]
            orchestrator.stop()
            logger.info(f"[WebSocket] Signaled orchestrator to stop for {session_id}")

    async def start_discussion(self, session_id: str, config: CouncilConfig):
        """Start or resume a discussion."""
        orchestrator = CouncilOrchestrator(config)
        self.active_discussions[session_id] = orchestrator

        # Send initial state
        await self._send_message(session_id, {
            "type": "state",
            "state": orchestrator.get_state().model_dump(),
        })

        # Send existing segments if resuming a session
        if orchestrator.segments:
            for segment in orchestrator.segments:
                await self._send_message(session_id, {
                    "type": "segment",
                    "segment": segment.model_dump(),
                    "state": orchestrator.get_state().model_dump(),
                })

        # Send existing turns if resuming a session
        if orchestrator.turns:
            for turn in orchestrator.turns:
                await self._send_message(session_id, {
                    "type": "turn",
                    "turn": turn.model_dump(),
                    "state": orchestrator.get_state().model_dump(),
                })

        # Start discussion loop
        asyncio.create_task(self._run_discussion_loop(session_id))

    async def _run_discussion_loop(self, session_id: str):
        """Run the discussion loop for a session."""
        orchestrator = self.active_discussions.get(session_id)
        if not orchestrator:
            logger.error(f"[WebSocket] No orchestrator found for session: {session_id}")
            return

        logger.info(f"[WebSocket] Starting discussion loop for session: {session_id}")

        try:
            while orchestrator._should_continue():
                # Check if client is still connected
                if session_id not in self.connections:
                    logger.info(f"[WebSocket] Client disconnected, stopping discussion for {session_id}")
                    break

                logger.debug(f"[WebSocket] Running turn {orchestrator.current_turn + 1} for {session_id}")

                # Run single turn
                turn = await orchestrator.run_single_turn(
                    progress_callback=lambda event_type, data: self._handle_progress(session_id, event_type, data)
                )

                if turn:
                    await self._send_message(session_id, {
                        "type": "turn",
                        "turn": turn.model_dump(),
                        "state": orchestrator.get_state().model_dump(),
                    })
                else:
                    logger.warning(f"[WebSocket] No turn returned for {session_id}")

                # Small delay between turns
                await asyncio.sleep(0.5)

            # Discussion complete
            logger.info(f"[WebSocket] Discussion complete for session: {session_id}")
            summary = await orchestrator._generate_summary(orchestrator.start_time)

            # Save final session state to SQLite with completed status
            if orchestrator.config.session_id:
                from app.core.database import db
                db.save_session_full(
                    session_id=orchestrator.config.session_id,
                    topic=orchestrator.config.topic,
                    config=orchestrator.config,
                    turns=orchestrator.turns,
                    segments=orchestrator.segments,
                    current_turn=orchestrator.current_turn,
                    current_segment=orchestrator.current_segment,
                    total_tokens=orchestrator.total_tokens_used,
                    status='completed',
                    summary=summary.model_dump(),
                    start_time=orchestrator.start_time,
                    end_time=time.time(),
                )
                logger.info(f"[WebSocket] Final session state saved to database for: {session_id}")

            await self._send_message(session_id, {
                "type": "complete",
                "summary": summary.model_dump(),
                "state": {**orchestrator.get_state().model_dump(), "is_running": False, "status": "completed"},
            })

        except Exception as e:
            logger.error(f"[WebSocket] Error in discussion loop for {session_id}: {e}")
            try:
                await self._send_message(session_id, {
                    "type": "error",
                    "error": str(e),
                })
            except Exception as send_err:
                logger.error(f"[WebSocket] Failed to send error message: {send_err}")

    async def _handle_progress(self, session_id: str, event_type: str, data):
        """Handle progress updates from orchestrator."""
        orchestrator = self.active_discussions.get(session_id)
        if not orchestrator:
            return

        if event_type == "thinking":
            await self._send_message(session_id, {
                "type": "state",
                "state": {**orchestrator.get_state().model_dump(), "current_agent": data, "status": "thinking"},
            })

        elif event_type == "segment":
            await self._send_message(session_id, {
                "type": "segment",
                "segment": data.model_dump(),
                "state": orchestrator.get_state().model_dump(),
            })

        elif event_type == "orchestrator":
            await self._send_message(session_id, {
                "type": "orchestrator",
                "message": data,
                "state": orchestrator.get_state().model_dump(),
            })

        elif event_type == "insights":
            # Handle insights update - data is a dict with "insights" and "total_count"
            insights_data = data.get("insights", [])
            total_count = data.get("total_count", len(insights_data))
            logger.info(f"[WebSocket] Sending {len(insights_data)} insights to client for session {session_id}")
            await self._send_message(session_id, {
                "type": "insights",
                "insights": [insight.model_dump() for insight in insights_data],
                "total_count": total_count,
                "state": orchestrator.get_state().model_dump(),
            })

        # New detailed progress events
        elif event_type.startswith("agent_"):
            await self._send_message(session_id, {
                "type": "progress",
                "event": event_type,
                "data": data,
                "state": orchestrator.get_state().model_dump(),
            })

    async def handle_user_message(self, session_id: str, content: str):
        """Handle a user message during discussion."""
        from datetime import datetime
        orchestrator = self.active_discussions.get(session_id)
        if orchestrator:
            orchestrator.add_user_message(content)
            await self._send_message(session_id, {
                "type": "turn",
                "turn": DiscussionTurn(
                    turn_number=orchestrator.current_turn + 0.1,
                    agent_name="You",
                    persona="Human",
                    content=content,
                    timestamp=datetime.now().timestamp(),
                    tool_calls=[],
                    tool_results=[],
                    segment=orchestrator.current_segment,
                ).model_dump(),
                "state": orchestrator.get_state().model_dump(),
            })

    async def _send_message(self, session_id: str, message: dict):
        """Send a message to a WebSocket client."""
        websocket = self.connections.get(session_id)
        if websocket:
            try:
                await websocket.send_json(message)
                logger.info(f"[WebSocket] Sent {message.get('type')} to {session_id}, insights count: {len(message.get('insights', []))}")
            except Exception as e:
                logger.error(f"[WebSocket] Failed to send message to {session_id}: {e}")
                # Connection is likely broken, clean it up
                self.disconnect(session_id)
        else:
            logger.warning(f"[WebSocket] No connection found for {session_id}")


# Global discussion manager
manager = DiscussionManager()


async def handle_websocket(websocket: WebSocket, session_id: str):
    """Handle WebSocket connection (already accepted)."""
    logger.info(f"[WebSocket] Handling connection for session: {session_id}")

    try:
        await manager.connect(websocket, session_id)
    except Exception as e:
        logger.error(f"[WebSocket] Failed to track connection for {session_id}: {e}")
        return

    try:
        while True:
            # Receive messages from client
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError as e:
                logger.error(f"[WebSocket] Invalid JSON from {session_id}: {e}")
                await websocket.send_json({"type": "error", "error": "Invalid JSON"})
                continue
            except WebSocketDisconnect:
                logger.info(f"[WebSocket] Client disconnected: {session_id}")
                break
            except Exception as e:
                logger.error(f"[WebSocket] Error receiving from {session_id}: {e}")
                break

            msg_type = data.get("type")

            if msg_type == "start":
                try:
                    logger.info(f"[WebSocket] Starting discussion for: {session_id}")
                    config = CouncilConfig(**data.get("config", {}))
                    await manager.start_discussion(session_id, config)
                except Exception as e:
                    logger.error(f"[WebSocket] Error starting discussion: {e}")
                    await websocket.send_json({"type": "error", "error": str(e)})

            elif msg_type == "user_message":
                try:
                    await manager.handle_user_message(session_id, data.get("content", ""))
                except Exception as e:
                    logger.error(f"[WebSocket] Error handling message: {e}")
                    await websocket.send_json({"type": "error", "error": str(e)})

            elif msg_type == "stop":
                try:
                    logger.info(f"[WebSocket] Stop requested for: {session_id}")
                    manager.stop_discussion(session_id)
                    await websocket.send_json({"type": "stopped", "message": "Discussion stopping..."})
                except Exception as e:
                    logger.error(f"[WebSocket] Error stopping discussion: {e}")
                    import traceback
                    traceback.print_exc()
                    await websocket.send_json({"type": "error", "error": str(e)})

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "pause":
                pass

            elif msg_type == "resume":
                pass

            else:
                logger.warning(f"[WebSocket] Unknown type '{msg_type}' from {session_id}")

    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"[WebSocket] Unexpected error for {session_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except:
            pass
    finally:
        logger.info(f"[WebSocket] Cleaning up: {session_id}")
        manager.disconnect(session_id)
