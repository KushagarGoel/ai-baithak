"""SQLite database for session persistence."""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from app.models.schemas import CouncilConfig, DiscussionTurn, DiscussionSegment


class SessionDatabase:
    """SQLite database for storing discussion sessions."""

    def __init__(self, db_path: str = "chats/sessions.db"):
        self.db_path = os.path.abspath(db_path)
        print(f"[DB] Initializing database at: {self.db_path}")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        print(f"[DB] Database initialized")

    def _init_db(self):
        """Initialize database tables."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    config TEXT NOT NULL,
                    current_turn INTEGER DEFAULT 0,
                    current_segment INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    start_time TEXT,
                    end_time TEXT,
                    status TEXT DEFAULT 'active',
                    summary TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migration: Add status column if it doesn't exist (for existing databases)
            try:
                conn.execute("SELECT status FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                conn.execute("ALTER TABLE sessions ADD COLUMN status TEXT DEFAULT 'active'")
                print("[DB MIGRATION] Added 'status' column to sessions table")

            # Migration: Add summary column if it doesn't exist
            try:
                conn.execute("SELECT summary FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
                print("[DB MIGRATION] Added 'summary' column to sessions table")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_number REAL NOT NULL,
                    agent_name TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    tool_calls TEXT,
                    tool_results TEXT,
                    segment INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    UNIQUE(session_id, turn_number)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    segment_number INTEGER NOT NULL,
                    start_turn INTEGER NOT NULL,
                    end_turn INTEGER,
                    summary TEXT,
                    orchestrator_message TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    UNIQUE(session_id, segment_number)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_segments_session ON segments(session_id)
            """)

            # Insights table for storing key insights from orchestrator
            conn.execute("""
                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    insight_number INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'orchestrator',
                    source_agent TEXT,
                    turn_number REAL,
                    segment INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    UNIQUE(session_id, insight_number)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_insights_session ON insights(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_insights_segment ON insights(session_id, segment)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC)
            """)

    @contextmanager
    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_session(self, session_id: str, topic: str, config: CouncilConfig,
                     current_turn: int, current_segment: int, total_tokens: int,
                     start_time: Optional[float] = None):
        """Save or update session metadata."""
        start_time_str = datetime.fromtimestamp(start_time).isoformat() if start_time else None
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO sessions (session_id, topic, config, current_turn, current_segment,
                                     total_tokens, start_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    current_turn = excluded.current_turn,
                    current_segment = excluded.current_segment,
                    total_tokens = excluded.total_tokens,
                    start_time = excluded.start_time,
                    updated_at = CURRENT_TIMESTAMP
            """, (session_id, topic, config.model_dump_json(), current_turn,
                  current_segment, total_tokens, start_time_str))

    def save_turn(self, session_id: str, turn: DiscussionTurn):
        """Save a turn to the database."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO turns
                (session_id, turn_number, agent_name, persona, content, timestamp,
                 tool_calls, tool_results, segment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, turn.turn_number, turn.agent_name, turn.persona,
                  turn.content, turn.timestamp,
                  json.dumps([t.model_dump() if hasattr(t, 'model_dump') else t for t in turn.tool_calls]),
                  json.dumps([t.model_dump() if hasattr(t, 'model_dump') else t for t in turn.tool_results]),
                  turn.segment))

    def save_segment(self, session_id: str, segment: DiscussionSegment):
        """Save a segment to the database."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO segments
                (session_id, segment_number, start_turn, end_turn, summary, orchestrator_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, segment.segment_number, segment.start_turn,
                  segment.end_turn, segment.summary, segment.orchestrator_message))

    def load_session(self, session_id: str) -> Optional[dict]:
        """Load session data including turns and segments."""
        with self._get_conn() as conn:
            # Load session metadata
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if not row:
                return None

            session = dict(row)
            session['config'] = json.loads(session['config'])

            # Load turns
            turns = conn.execute(
                "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_number",
                (session_id,)
            ).fetchall()
            session['turns'] = []
            for t in turns:
                turn = dict(t)
                turn['tool_calls'] = json.loads(turn['tool_calls'] or '[]')
                turn['tool_results'] = json.loads(turn['tool_results'] or '[]')
                session['turns'].append(turn)

            # Load segments
            segments = conn.execute(
                "SELECT * FROM segments WHERE session_id = ? ORDER BY segment_number",
                (session_id,)
            ).fetchall()
            session['segments'] = [dict(s) for s in segments]

            return session

    def get_all_sessions(self) -> list[dict]:
        """Get all sessions ordered by most recent update."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT session_id, topic, current_turn, updated_at FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        print(f"[DB] Checking if session exists: {session_id}")
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            exists = row is not None
            print(f"[DB] Session {session_id} exists: {exists}")
            return exists

    def save_session_full(self, session_id: str, topic: str, config: CouncilConfig,
                          turns: list[DiscussionTurn], segments: list[DiscussionSegment],
                          current_turn: int, current_segment: int, total_tokens: int,
                          status: str = 'active', summary: Optional[dict] = None,
                          start_time: Optional[float] = None, end_time: Optional[float] = None,
                          last_saved_turn: int = 0):
        """Save complete session state including turns and segments in a single transaction.

        This is the primary method for persisting session context to SQLite.
        Optimized to only save new turns since last_saved_turn.
        """
        start_time_str = datetime.fromtimestamp(start_time).isoformat() if start_time else None
        end_time_str = datetime.fromtimestamp(end_time).isoformat() if end_time else None
        summary_json = json.dumps(summary) if summary else None

        with self._get_conn() as conn:
            # Save session metadata
            conn.execute("""
                INSERT INTO sessions (session_id, topic, config, current_turn, current_segment,
                                     total_tokens, start_time, end_time, status, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    topic = excluded.topic,
                    config = excluded.config,
                    current_turn = excluded.current_turn,
                    current_segment = excluded.current_segment,
                    total_tokens = excluded.total_tokens,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    status = excluded.status,
                    summary = excluded.summary,
                    updated_at = CURRENT_TIMESTAMP
            """, (session_id, topic, config.model_dump_json(), current_turn,
                  current_segment, total_tokens, start_time_str, end_time_str,
                  status, summary_json))

            # Only save new turns (after last_saved_turn)
            # This avoids O(n^2) behavior of saving all turns every time
            new_turns = [t for t in turns if t.turn_number > last_saved_turn]
            for turn in new_turns:
                conn.execute("""
                    INSERT OR REPLACE INTO turns
                    (session_id, turn_number, agent_name, persona, content, timestamp,
                     tool_calls, tool_results, segment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, turn.turn_number, turn.agent_name, turn.persona,
                      turn.content, turn.timestamp,
                      json.dumps([t.model_dump() if hasattr(t, 'model_dump') else t for t in turn.tool_calls]),
                      json.dumps([t.model_dump() if hasattr(t, 'model_dump') else t for t in turn.tool_results]),
                      turn.segment))

            # Only save segments that have changed (check if they already exist)
            for segment in segments:
                conn.execute("""
                    INSERT OR REPLACE INTO segments
                    (session_id, segment_number, start_turn, end_turn, summary, orchestrator_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, segment.segment_number, segment.start_turn,
                      segment.end_turn, segment.summary, segment.orchestrator_message))

            return len(new_turns)

    def load_session_full(self, session_id: str) -> Optional[dict]:
        """Load complete session state including turns, segments, and insights.

        This is the primary method for restoring session context from SQLite.
        """
        session = self.load_session(session_id)
        if not session:
            return None

        # Load insights
        session['insights'] = self.get_insights(session_id)

        return session

    def delete_session_full(self, session_id: str) -> bool:
        """Delete a session and all its associated data (turns, segments, insights)."""
        with self._get_conn() as conn:
            # Delete insights first (foreign key constraint)
            conn.execute("DELETE FROM insights WHERE session_id = ?", (session_id,))
            # Delete segments
            conn.execute("DELETE FROM segments WHERE session_id = ?", (session_id,))
            # Delete turns
            conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            # Delete session
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return conn.total_changes > 0

    def list_sessions_full(self) -> list[dict]:
        """Get all sessions with their metadata."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT session_id, topic, current_turn, current_segment,
                          total_tokens, status, start_time, end_time, updated_at
                   FROM sessions ORDER BY updated_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]

    def save_insight(self, session_id: str, content: str, source: str = 'orchestrator',
                     source_agent: Optional[str] = None, turn_number: Optional[float] = None,
                     segment: int = 0) -> int:
        """Save a key insight to the database.

        Returns:
            The insight_number assigned to this insight.
        """
        with self._get_conn() as conn:
            # Get the next insight number for this session
            row = conn.execute(
                "SELECT COALESCE(MAX(insight_number), 0) + 1 FROM insights WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            insight_number = row[0] if row else 1

            conn.execute("""
                INSERT INTO insights
                (session_id, insight_number, content, source, source_agent, turn_number, segment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, insight_number, content, source, source_agent, turn_number, segment))

            return insight_number

    def save_insights_batch(self, session_id: str, insights: list[str], source: str = 'orchestrator',
                            source_agent: Optional[str] = None, turn_number: Optional[float] = None,
                            segment: int = 0) -> list[int]:
        """Save multiple insights in a batch.

        Returns:
            List of insight_numbers assigned.
        """
        insight_numbers = []
        with self._get_conn() as conn:
            # Get the next insight number for this session
            row = conn.execute(
                "SELECT COALESCE(MAX(insight_number), 0) + 1 FROM insights WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            next_number = row[0] if row else 1

            for i, content in enumerate(insights):
                insight_number = next_number + i
                conn.execute("""
                    INSERT INTO insights
                    (session_id, insight_number, content, source, source_agent, turn_number, segment)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, insight_number, content, source, source_agent, turn_number, segment))
                insight_numbers.append(insight_number)

            return insight_numbers

    def get_insights(self, session_id: str, segment: Optional[int] = None) -> list[dict]:
        """Get all insights for a session, optionally filtered by segment."""
        with self._get_conn() as conn:
            if segment is not None:
                rows = conn.execute(
                    """SELECT * FROM insights
                       WHERE session_id = ? AND segment = ?
                       ORDER BY insight_number ASC""",
                    (session_id, segment)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM insights
                       WHERE session_id = ?
                       ORDER BY insight_number ASC""",
                    (session_id,)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_insight_count(self, session_id: str) -> int:
        """Get the total number of insights for a session."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM insights WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            return row[0] if row else 0


# Global database instance
db = SessionDatabase()
