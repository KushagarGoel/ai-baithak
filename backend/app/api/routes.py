"""API routes for the Agent Council backend."""

import os
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

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
from app.core.report_service import ReportService

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
    print(f"[API] Getting insights for session: {session_id}, segment: {segment}")
    try:
        # Check if session exists
        exists = db.session_exists(session_id)
        print(f"[API] Session exists: {exists}")
        if not exists:
            # Return empty insights for non-existent session
            print(f"[API] Session {session_id} not found, returning empty")
            return {
                "insights": [],
                "total_count": 0,
                "session_id": session_id,
            }

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
        print(f"[API ERROR] Failed to get insights for {session_id}: {e}")
        # Return empty insights on error instead of 500
        return {
            "insights": [],
            "total_count": 0,
            "session_id": session_id,
            "error": str(e),
        }


@router.get("/sessions/{session_id}/report")
async def get_session_report(session_id: str):
    """Get the comprehensive solutioning report for a completed session."""
    try:
        session_data = db.load_session_full(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Parse summary JSON if exists
        summary_data = {}
        if session_data.get('summary'):
            try:
                summary_data = json.loads(session_data['summary'])
            except json.JSONDecodeError:
                pass

        # If no summary or summary is minimal, return 404
        if not summary_data:
            raise HTTPException(status_code=404, detail="Report not yet generated for this session")

        # Parse config for agent info
        config = session_data.get('config', {})
        if isinstance(config, str):
            config = json.loads(config)

        # Build the comprehensive report
        report = {
            "session_id": session_id,
            "topic": summary_data.get('topic', session_data.get('topic', 'Unknown Topic')),
            "status": session_data.get('status', 'unknown'),
            "start_time": summary_data.get('start_time', session_data.get('start_time')),
            "end_time": summary_data.get('end_time', session_data.get('end_time')),
            "total_turns": summary_data.get('total_turns', session_data.get('current_turn', 0)),

            # Problem & Solution Overview
            "problem_statement": summary_data.get('problem_statement', ''),
            "final_answer": summary_data.get('final_answer', ''),
            "justification": summary_data.get('justification', ''),
            "final_recommendation": summary_data.get('final_recommendation', ''),

            # Solution Options
            "solution_options": summary_data.get('solution_options', []),
            "selected_solution": summary_data.get('selected_solution'),
            "selection_reasoning": summary_data.get('selection_reasoning', ''),

            # Implementation & Risks
            "implementation_steps": summary_data.get('implementation_steps', []),
            "risks_and_mitigations": summary_data.get('risks_and_mitigations', []),
            "action_items": summary_data.get('action_items', []),

            # Consensus & Disagreements
            "consensus_reached": summary_data.get('consensus_reached', False),
            "key_points": summary_data.get('key_points', []),
            "disagreements": summary_data.get('disagreements', []),

            # Segment Reports
            "segment_reports": summary_data.get('segment_reports', []),

            # Agent Analyses
            "agent_analyses": summary_data.get('agent_analyses', []),

            # Raw turns data for reference
            "turns": session_data.get('turns', []),
            "segments": session_data.get('segments', []),
        }

        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.post("/sessions/{session_id}/generate-report")
async def generate_session_report(
    session_id: str,
    request_data: dict = None
):
    """Generate a report on-demand for any session (active or completed).

    Args:
        session_id: The session ID
        request_data: Optional dict with custom_instructions and model

    Returns:
        The generated report data
    """
    try:
        # Check if session exists
        if not db.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        # Load session to get config with litellm_proxy
        session_data = db.load_session_full(session_id)
        config_data = session_data.get('config', {})
        if isinstance(config_data, str):
            config_data = json.loads(config_data)

        # Get custom instructions if provided
        custom_instructions = None
        model = None  # Use config's orchestrator_model by default
        if request_data:
            custom_instructions = request_data.get("custom_instructions")
            model = request_data.get("model")

        # Create report service with litellm_proxy from config
        litellm_proxy = config_data.get('litellm_proxy')
        report_service = ReportService(litellm_proxy=litellm_proxy)

        # Generate report
        summary = await report_service.generate_report(
            session_id=session_id,
            custom_instructions=custom_instructions,
            model=model
        )

        # Convert to dict for response
        report_data = summary.model_dump()
        report_data["session_id"] = session_id
        report_data["status"] = "generated"

        return {
            "success": True,
            "message": "Report generated successfully",
            "report": report_data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/sessions/{session_id}/report-pdf")
async def download_report_pdf(session_id: str):
    """Download the session report as a PDF.

    Args:
        session_id: The session ID

    Returns:
        PDF file download
    """
    try:
        # Get existing report from database (fresh data)
        report_service = ReportService()
        report = report_service.get_existing_report(session_id)

        if not report:
            raise HTTPException(status_code=404, detail="Report not found. Generate a report first.")

        # Refresh from database to ensure we have latest
        session_data = db.load_session_full(session_id)
        if session_data and session_data.get('summary'):
            try:
                summary_data = json.loads(session_data['summary'])
                # Merge fresh summary data
                report.update(summary_data)
            except json.JSONDecodeError:
                pass

        # Generate PDF (placeholder - will implement with proper PDF library)
        # For now, return markdown as a downloadable file
        from io import StringIO

        # Build markdown content
        md_content = f"""# Solutioning Report: {report['topic']}

**Session ID:** {session_id}
**Status:** {report['status']}
**Turns:** {report['total_turns']}
**Date:** {report['start_time'][:10] if report['start_time'] else 'N/A'}

---

## Problem Statement

{report['problem_statement'] or 'No problem statement available.'}

## Final Answer

{report['final_answer'] or 'No final answer available.'}

## Justification

{report['justification'] or 'No justification available.'}

---

## Solution Options

"""
        for i, option in enumerate(report.get('solution_options', []), 1):
            md_content += f"""### {i}. {option.get('option_name', 'Unnamed')}

{option.get('description', 'No description.')}

**Pros:**
"""
            for pro in option.get('pros', []):
                md_content += f"- {pro}\n"

            md_content += "\n**Cons:**\n"
            for con in option.get('cons', []):
                md_content += f"- {con}\n"

            if option.get('supporters'):
                md_content += f"\n**Supporters:** {', '.join(option['supporters'])}\n"
            if option.get('opposers'):
                md_content += f"**Opposers:** {', '.join(option['opposers'])}\n"
            md_content += "\n---\n\n"

        if report.get('selected_solution'):
            md_content += f"""## Selected Solution

**{report['selected_solution']}**

{report.get('selection_reasoning', 'No reasoning provided.')}

---

"""

        md_content += f"""## Implementation Steps

"""
        for i, step in enumerate(report.get('implementation_steps', []), 1):
            md_content += f"{i}. {step}\n"

        if not report.get('implementation_steps'):
            md_content += "No implementation steps defined.\n"

        md_content += f"""

## Risks & Mitigations

"""
        for risk in report.get('risks_and_mitigations', []):
            md_content += f"- {risk}\n"

        if not report.get('risks_and_mitigations'):
            md_content += "No risks identified.\n"

        md_content += f"""

## Action Items

"""
        for i, item in enumerate(report.get('action_items', []), 1):
            md_content += f"{i}. [ ] {item}\n"

        if not report.get('action_items'):
            md_content += "No action items defined.\n"

        md_content += f"""

---

## Segment Reports

"""
        for seg in report.get('segment_reports', []):
            md_content += f"""### Segment {seg.get('segment_number', '?')}

{seg.get('summary', 'No summary available.')}

"""
            if seg.get('key_developments'):
                md_content += "**Key Developments:**\n"
                for dev in seg['key_developments']:
                    md_content += f"- {dev}\n"
                md_content += "\n"

            if seg.get('decisions_made'):
                md_content += "**Decisions Made:**\n"
                for dec in seg['decisions_made']:
                    md_content += f"- {dec}\n"
                md_content += "\n"

        md_content += f"""

---

## Agent Analyses

"""
        for agent in report.get('agent_analyses', []):
            md_content += f"""### {agent.get('agent_name', 'Unknown')} ({agent.get('persona', 'Unknown')})

**Stance:** {agent.get('stance', 'N/A')}

"""
            if agent.get('critical_points'):
                md_content += "**Critical Points:**\n"
                for point in agent['critical_points']:
                    md_content += f"- {point}\n"
                md_content += "\n"

            if agent.get('tools_used'):
                md_content += f"**Tools Used:** {', '.join(agent['tools_used'])}\n"

            md_content += "\n---\n\n"

        md_content += f"""## Key Points

"""
        for point in report.get('key_points', []):
            md_content += f"- {point}\n"

        if report.get('disagreements'):
            md_content += f"""

## Areas of Disagreement

"""
            for d in report['disagreements']:
                md_content += f"- {d}\n"

        md_content += f"""

---

## Final Recommendation

{report.get('final_recommendation', 'No recommendation available.')}

---

*Generated by Agent Council*
"""

        # Create response
        buffer = StringIO(md_content)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=report_{session_id}.md"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
