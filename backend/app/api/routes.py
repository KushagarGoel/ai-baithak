"""API routes for the Agent Council backend."""

import os
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.schemas import (
    Session,
    ArchiveItem,
    DiscussionSummary,
    CouncilConfig,
    KeyInsight,
    DiscussionTurn,
    DiscussionSegment,
)
from app.core.database import db
from app.core.config import settings

router = APIRouter()


@router.get("/sessions")
async def list_sessions():
    """List all saved sessions from SQLite."""
    try:
        sessions_data = db.list_sessions_full()
        sessions = []
        for data in sessions_data:
            sessions.append(Session(
                id=data['session_id'],
                topic=data['topic'],
                turns=data['current_turn'],
                date=data['updated_at'],
                total_tokens=data['total_tokens'],
                current_segment=data['current_segment'],
            ))
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session with all turns, segments, and insights from SQLite."""
    try:
        session_data = db.load_session_full(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Parse config from JSON string
        if isinstance(session_data.get('config'), str):
            session_data['config'] = json.loads(session_data['config'])

        return session_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load session: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its data from SQLite."""
    try:
        deleted = db.delete_session_full(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("/archives")
async def list_archives():
    """List all archived (completed) discussions from SQLite."""
    try:
        # Get completed sessions from database
        sessions_data = db.list_sessions_full()
        archives = []

        for data in sessions_data:
            if data.get('status') != 'completed':
                continue

            # Parse summary JSON if exists
            summary_data = {}
            if data.get('summary'):
                try:
                    summary_data = json.loads(data['summary'])
                except json.JSONDecodeError:
                    pass

            archives.append(ArchiveItem(
                id=data['session_id'],
                summary=DiscussionSummary(
                    topic=data['topic'],
                    start_time=data.get('start_time') or datetime.now().isoformat(),
                    end_time=data.get('end_time') or datetime.now().isoformat(),
                    total_turns=data['current_turn'],
                    key_points=summary_data.get('key_points', []),
                    consensus_reached=summary_data.get('consensus_reached', False),
                    disagreements=summary_data.get('disagreements', []),
                    action_items=summary_data.get('action_items', []),
                    final_recommendation=summary_data.get('final_recommendation'),
                ),
                transcript_path=f"chats/{data['session_id']}/transcript_{data['session_id']}.json",
                agent_count=0,  # Could be fetched from config if needed
                model_names=[],
            ))

        return {"archives": archives}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list archives: {str(e)}")


@router.get("/transcripts/{path:path}")
async def download_transcript(path: str):
    """Download a transcript file."""
    filepath = settings.WORKSPACE_PATH / path

    # Security check - ensure file is within workspace
    try:
        filepath.resolve().relative_to(settings.WORKSPACE_PATH.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")

    return FileResponse(filepath, filename=filepath.name)


@router.post("/sessions/{session_id}/save")
async def save_session(session_id: str, session_data: dict):
    """Save a session to SQLite.

    Expected session_data format:
    {
        "topic": str,
        "config": dict,
        "turns": list[DiscussionTurn],
        "segments": list[DiscussionSegment],
        "current_turn": int,
        "current_segment": int,
        "total_tokens": int,
        "status": str,
        "summary": dict (optional),
        "start_time": float (optional),
        "end_time": float (optional)
    }
    """
    try:
        # Convert dict turns to DiscussionTurn objects
        turns = []
        for turn_data in session_data.get('turns', []):
            turns.append(DiscussionTurn(**turn_data))

        # Convert dict segments to DiscussionSegment objects
        segments = []
        for seg_data in session_data.get('segments', []):
            segments.append(DiscussionSegment(**seg_data))

        # Convert config dict to CouncilConfig
        config_data = session_data.get('config', {})
        config = CouncilConfig(**config_data)

        # Save to SQLite
        db.save_session_full(
            session_id=session_id,
            topic=session_data.get('topic', config.topic),
            config=config,
            turns=turns,
            segments=segments,
            current_turn=session_data.get('current_turn', 0),
            current_segment=session_data.get('current_segment', 0),
            total_tokens=session_data.get('total_tokens', 0),
            status=session_data.get('status', 'active'),
            summary=session_data.get('summary'),
            start_time=session_data.get('start_time'),
            end_time=session_data.get('end_time'),
        )

        return {"message": "Session saved to database"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")


@router.get("/sessions/{session_id}/insights")
async def get_session_insights(session_id: str, segment: Optional[int] = Query(None)):
    """Get key insights for a session."""
    try:
        insights_data = db.get_insights(session_id, segment)
        insights = [
            KeyInsight(
                id=insight['id'],
                insight_number=insight['insight_number'],
                content=insight['content'],
                source=insight['source'],
                source_agent=insight['source_agent'],
                turn_number=insight['turn_number'],
                segment=insight['segment'],
                created_at=insight['created_at'],
            )
            for insight in insights_data
        ]
        return {
            "insights": insights,
            "total_count": len(insights),
            "session_id": session_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")
