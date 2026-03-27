"""Orchestrator for managing council discussions."""

import asyncio
import json
import os
import re
import time
import random
from datetime import datetime
from typing import Optional, Callable

from litellm import completion

from app.models.schemas import (
    CouncilConfig,
    DiscussionTurn,
    DiscussionSegment,
    DiscussionSummary,
    OrchestratorState,
    LiteLLMProxyConfig,
)
from app.core.agent import CouncilAgent, AgentConfig
from app.core.personas import get_persona
from app.core.database import db
from app.mcp.tools import MCPToolServer


class CouncilOrchestrator:
    """Orchestrates the agent council discussion."""

    def __init__(self, config: CouncilConfig, load_from_transcript: bool = True):
        self.config = config
        self.agents: list[CouncilAgent] = []
        self.turns: list[DiscussionTurn] = []
        self.segments: list[DiscussionSegment] = []
        self.start_time: Optional[float] = None
        self.current_turn = 0
        self.current_segment = 0
        self.total_tokens_used = 0
        self.segment_tokens_used = 0  # Tokens used in current segment only
        self._pending_segment_transition = False
        self._last_saved_turn = 0  # Track last turn saved to database
        self._stop_requested = False  # Flag to stop discussion
        self._setup_agents()

        # Try to load existing session
        if load_from_transcript and config.session_id:
            self._load_from_transcript()
        else:
            # Initialize first segment for new session
            self.segments.append(DiscussionSegment(
                segment_number=0,
                start_turn=1,
                summary="",
                orchestrator_message=""
            ))

    def _load_from_transcript(self):
        """Load session state from database or transcript."""
        if not self.config.session_id:
            return

        # Try database first
        try:
            session_data = db.load_session(self.config.session_id)
            if session_data:
                self._load_from_database(session_data)
                return
        except Exception as e:
            print(f"[DB LOAD ERROR] {e}, falling back to transcript")

        # Fallback to transcript file
        transcript_path = os.path.join(
            self.config.workspace_path, "chats", self.config.session_id,
            f"transcript_{self.config.session_id}.json"
        )

        if not os.path.exists(transcript_path):
            # No existing transcript, start fresh
            self.segments.append(DiscussionSegment(
                segment_number=0,
                start_turn=1,
                summary="",
                orchestrator_message=""
            ))
            return

        try:
            with open(transcript_path, "r") as f:
                transcript = json.load(f)

            # Restore turns
            for t in transcript.get("turns", []):
                from datetime import datetime
                turn = DiscussionTurn(
                    turn_number=t["turn_number"],
                    agent_name=t["agent"],
                    persona=t["persona"],
                    content=t["content"],
                    timestamp=datetime.fromisoformat(t["timestamp"]).timestamp() if t.get("timestamp") else time.time(),
                    tool_calls=t.get("tool_calls", []),
                    tool_results=t.get("tool_results", []),
                    segment=t.get("segment", 0),
                )
                self.turns.append(turn)
                self.current_turn = max(self.current_turn, int(t["turn_number"]))

            # Restore segments
            for s in transcript.get("segments", []):
                segment = DiscussionSegment(
                    segment_number=s["segment_number"],
                    start_turn=s["start_turn"],
                    end_turn=s.get("end_turn"),
                    summary=s.get("summary", ""),
                    orchestrator_message=s.get("orchestrator_message", ""),
                )
                self.segments.append(segment)
                self.current_segment = max(self.current_segment, s["segment_number"])

            # Restore agent message histories
            for turn in self.turns:
                message = f"{turn.agent_name} ({turn.persona}): {turn.content}"
                for agent in self.agents:
                    if agent.config.name != turn.agent_name:
                        agent.add_message("user", message)

            # Restore total tokens
            self.total_tokens_used = transcript.get("total_tokens", 0)

            print(f"[SESSION LOADED] Restored {len(self.turns)} turns from {transcript_path}")

        except Exception as e:
            print(f"[SESSION LOAD ERROR] {e}")
            # Start fresh on error
            self.segments.append(DiscussionSegment(
                segment_number=0,
                start_turn=1,
                summary="",
                orchestrator_message=""
            ))

    def _load_from_database(self, session_data: dict):
        """Load session from database."""
        # Restore turns
        for t in session_data.get("turns", []):
            turn = DiscussionTurn(
                turn_number=t["turn_number"],
                agent_name=t["agent_name"],
                persona=t["persona"],
                content=t["content"],
                timestamp=t["timestamp"],
                tool_calls=t.get("tool_calls", []),
                tool_results=t.get("tool_results", []),
                segment=t.get("segment", 0),
            )
            self.turns.append(turn)
            self.current_turn = max(self.current_turn, int(t["turn_number"]))

        # Restore segments
        for s in session_data.get("segments", []):
            segment = DiscussionSegment(
                segment_number=s["segment_number"],
                start_turn=s["start_turn"],
                end_turn=s.get("end_turn"),
                summary=s.get("summary", ""),
                orchestrator_message=s.get("orchestrator_message", ""),
            )
            self.segments.append(segment)
            self.current_segment = max(self.current_segment, s["segment_number"])

        # Restore agent message histories
        for turn in self.turns:
            message = f"{turn.agent_name} ({turn.persona}): {turn.content}"
            for agent in self.agents:
                if agent.config.name != turn.agent_name:
                    agent.add_message("user", message)

        # Restore total tokens
        self.total_tokens_used = session_data.get("total_tokens", 0)

        print(f"[SESSION LOADED] Restored {len(self.turns)} turns from database")

    def _setup_agents(self):
        """Initialize all council agents with per-agent tool servers."""
        from app.core.database import db

        for agent_config in self.config.agents:
            # Resolve agent_id from persona if not provided
            agent_id = agent_config.agent_id
            if not agent_id:
                # Look up agent by persona name
                persona_key = agent_config.persona.lower().replace(" ", "_")
                agent_id = f"persona_{persona_key}"
                # Verify it exists in database
                agent_data = db.get_agent(agent_id)
                if not agent_data:
                    # Try alternate format
                    agent_id = None

            # Create per-agent tool server with agent_id for MCP access
            tool_server = MCPToolServer(
                base_path=self.config.workspace_path,
                agent_id=agent_id
            )
            agent = CouncilAgent(
                config=agent_config,
                tool_server=tool_server,
                litellm_proxy=self.config.litellm_proxy,
                agent_id=agent_id,
            )
            self.agents.append(agent)

    def get_state(self) -> OrchestratorState:
        """Get current orchestrator state."""
        return OrchestratorState(
            current_turn=self.current_turn,
            max_turns=self.config.max_turns,
            current_segment=self.current_segment,
            total_segments=len(self.segments),
            segment_tokens=self.segment_tokens_used,
            total_tokens=self.total_tokens_used,
            is_running=self._should_continue(),
            status="thinking",
        )

    def _should_continue(self) -> bool:
        """Determine if discussion should continue."""
        if self._stop_requested:
            return False

        if self.start_time is None:
            return True

        elapsed_minutes = (time.time() - self.start_time) / 60

        if elapsed_minutes >= self.config.max_duration_minutes:
            return False

        if self.current_turn < self.config.min_turns:
            return True
        if self.current_turn >= self.config.max_turns:
            return False

        return True

    def stop(self):
        """Request to stop the discussion."""
        print(f"[ORCHESTRATOR] Stop requested for session {self.config.session_id}")
        self._stop_requested = True

        # Signal all agents to stop
        for agent in self.agents:
            agent.stop()

    async def run_discussion(self, progress_callback=None):
        """Run the full council discussion."""
        self.start_time = time.time()
        start_datetime = datetime.now()

        # Initial topic presentation
        initial_context = f"""Welcome to the Council Discussion.

TOPIC: {self.config.topic}

Guidelines:
- Engage authentically as your persona
- Listen to others and respond to their points
- Use tools when you need information
- Aim for depth over speed

Let's begin."""

        for agent in self.agents:
            agent.add_message("user", initial_context)

        # Run discussion loop
        while self._should_continue():
            self.current_turn += 1

            # Select next speaker
            speaker = self._select_next_speaker()
            if not speaker:
                break

            # Build context
            context = self._build_context_for_agent(speaker)

            # Get response
            if progress_callback:
                await progress_callback("thinking", speaker.config.name)

            response = await speaker.think_and_respond(context)
            self.total_tokens_used += response.get("tokens_used", 0)

            # Record turn
            turn = DiscussionTurn(
                turn_number=self.current_turn,
                agent_name=response["agent_name"],
                persona=response["persona"],
                content=response["content"],
                tool_calls=response.get("tool_calls", []),
                tool_results=response.get("tool_results", []),
                segment=self.current_segment,
            )
            self.turns.append(turn)

            if progress_callback:
                await progress_callback("turn", turn)

            # Broadcast to all other agents
            self._broadcast_turn(turn)

            # Check for segment transition
            await self._check_and_start_new_segment(progress_callback)

            # Orchestrator interjection
            if self.current_turn % self.config.orchestrator_frequency == 0:
                if progress_callback:
                    await progress_callback("orchestrating", None)
                await self._orchestrator_interjection(progress_callback)

        # Generate summary
        summary = await self._generate_summary(datetime.fromtimestamp(start_datetime) if isinstance(start_datetime, (int, float)) else start_datetime)

        # Save transcript
        if self.config.save_transcript:
            self._save_transcript()

        return summary

    async def run_single_turn(self, progress_callback=None):
        """Run a single turn (for WebSocket mode)."""
        if self.start_time is None:
            self.start_time = time.time()

            # Initial context on first turn
            initial_context = f"""Welcome to the Council Discussion.

TOPIC: {self.config.topic}

Guidelines:
- Engage authentically as your persona
- Listen to others and respond to their points
- Use tools when you need information

Let's begin."""
            for agent in self.agents:
                agent.add_message("user", initial_context)

        if not self._should_continue():
            return None

        self.current_turn += 1

        speaker = self._select_next_speaker()
        if not speaker:
            return None

        if progress_callback:
            await progress_callback("thinking", speaker.config.name)

        context = self._build_context_for_agent(speaker)

        # Create agent progress callback that forwards to main callback
        async def agent_progress(event_type: str, data: dict):
            if progress_callback:
                await progress_callback(f"agent_{event_type}", {
                    "agent": speaker.config.name,
                    **data
                })

        response = await speaker.think_and_respond(context, progress_callback=agent_progress)
        tokens_used = response.get("tokens_used", 0)
        self.total_tokens_used += tokens_used
        self.segment_tokens_used += tokens_used

        turn = DiscussionTurn(
            turn_number=self.current_turn,
            agent_name=response["agent_name"],
            persona=response["persona"],
            content=response["content"],
            tool_calls=response.get("tool_calls", []),
            tool_results=response.get("tool_results", []),
            segment=self.current_segment,
        )
        self.turns.append(turn)
        self._broadcast_turn(turn)

        # Save complete session context to SQLite
        if self.config.session_id:
            new_turns_count = db.save_session_full(
                session_id=self.config.session_id,
                topic=self.config.topic,
                config=self.config,
                turns=self.turns,
                segments=self.segments,
                current_turn=self.current_turn,
                current_segment=self.current_segment,
                total_tokens=self.total_tokens_used,
                status='active',
                start_time=self.start_time,
                last_saved_turn=self._last_saved_turn,
            )
            if new_turns_count > 0:
                self._last_saved_turn = self.current_turn

        # Check for segment transition
        await self._check_and_start_new_segment(progress_callback)

        # Orchestrator interjection
        print(f"[KEY INSIGHTS DEBUG] Checking interjection: turn={self.current_turn}, freq={self.config.orchestrator_frequency}, mod={self.current_turn % self.config.orchestrator_frequency}")
        if self.current_turn % self.config.orchestrator_frequency == 0:
            print(f"[KEY INSIGHTS DEBUG] Triggering orchestrator interjection")
            await self._orchestrator_interjection(progress_callback)

        return turn

    def _select_next_speaker(self) -> Optional[CouncilAgent]:
        """Select which agent speaks next."""
        willing_agents = [a for a in self.agents if a.should_speak()]
        if not willing_agents:
            willing_agents = self.agents

        last_speakers = [t.agent_name for t in self.turns[-len(self.agents):]]
        candidates = [(agent, last_speakers.count(agent.config.name)) for agent in willing_agents]
        candidates.sort(key=lambda x: x[1])

        top_candidates = candidates[:max(1, len(candidates) // 2)]
        return random.choice(top_candidates)[0]

    def _build_context_for_agent(self, agent: CouncilAgent) -> str:
        """Build context string for an agent's turn."""
        if not self.turns:
            return "Please share your initial thoughts on the topic."

        recent_turns = self.turns[-3:] if len(self.turns) >= 3 else self.turns
        context_parts = []
        for turn in recent_turns:
            context_parts.append(f"{turn.agent_name} ({turn.persona}): {turn.content}")
        context_parts.append(f"\nIt's your turn, {agent.config.name}. Respond to the discussion so far.")

        return "\n\n".join(context_parts)

    def _broadcast_turn(self, turn: DiscussionTurn):
        """Broadcast a turn to all agents."""
        message = f"{turn.agent_name} ({turn.persona}): {turn.content}"
        for agent in self.agents:
            if agent.config.name != turn.agent_name:
                agent.add_message("user", message)

    async def _check_and_start_new_segment(self, progress_callback=None):
        """Check if we need to start a new segment."""
        threshold = self.config.context_compression_threshold
        agents_needing_reset = [a for a in self.agents if len(a.messages) >= threshold]

        if not agents_needing_reset:
            return False

        print(f"[SEGMENT] {len(agents_needing_reset)} agent(s) exceeded {threshold} messages. Starting new segment...")
        await self._start_new_segment(progress_callback)
        return True

    async def _start_new_segment(self, progress_callback=None):
        """Start a new discussion segment."""
        detailed_summary = await self._generate_detailed_segment_summary()
        concise_summary = await self._generate_concise_summary()

        # Generate key insights for the segment that is ending
        # Must do this BEFORE incrementing current_segment
        print(f"[SEGMENT] Generating end-of-segment insights for segment {self.current_segment}")
        await self._save_key_insights_for_segment(progress_callback)

        # Close current segment
        current_seg = self.segments[self.current_segment]
        current_seg.end_turn = self.current_turn
        current_seg.summary = concise_summary

        # Create transition message
        transition_message = f"""[SEGMENT {self.current_segment + 1} - CONTINUED DISCUSSION]

**Original Topic:** {self.config.topic}

**What We've Covered:**
{detailed_summary[:800]}...

Continue the discussion from here, building on prior points while staying true to your persona."""

        current_seg.orchestrator_message = transition_message

        # Create new segment
        self.current_segment += 1
        new_segment = DiscussionSegment(
            segment_number=self.current_segment,
            start_turn=self.current_turn + 1,
            summary=concise_summary,
            orchestrator_message=transition_message
        )
        self.segments.append(new_segment)

        # Reset segment token counter for new segment
        self.segment_tokens_used = 0

        if progress_callback:
            await progress_callback("segment", new_segment)

        # Reset all agents
        for agent in self.agents:
            self._reset_agent_for_new_segment(agent, transition_message)

        # Add transition as a turn
        turn = DiscussionTurn(
            turn_number=self.current_turn + 0.5,
            agent_name="Orchestrator",
            persona="Manager",
            content=transition_message,
            segment=self.current_segment,
        )
        self.turns.append(turn)

        # Broadcast the transition turn so it's visible in UI
        if progress_callback:
            await progress_callback("turn", turn)

    def _reset_agent_for_new_segment(self, agent: CouncilAgent, transition_message: str):
        """Reset an agent's message history for a new segment."""
        system_message = None
        for msg in agent.messages:
            if msg.role == "system":
                system_message = msg
                break

        new_messages = []
        if system_message:
            new_messages.append(system_message)

        from app.core.agent import AgentMessage
        new_messages.append(AgentMessage(
            role="user",
            content=f"Original Topic: {self.config.topic}",
            agent_name="User"
        ))
        new_messages.append(AgentMessage(
            role="user",
            content=transition_message,
            agent_name="Orchestrator"
        ))

        agent.reset_messages(new_messages)

    async def _generate_detailed_segment_summary(self) -> str:
        """Generate a detailed summary for segment transition."""
        segment_turns = [t for t in self.turns if t.segment == self.current_segment]
        if not segment_turns:
            return "No prior discussion."

        discussion_text = "\n\n".join([
            f"{t.agent_name}: {t.content[:800]}"
            for t in segment_turns[-15:]
        ])

        prompt = f"""Summarize this council discussion segment:

**Key Arguments Made:**
**Points of Consensus:**
**Open Questions:**
**Critical Insights:**

Discussion:
{discussion_text}

Provide a detailed summary (max 1500 chars):"""

        try:
            model = self._get_orchestrator_model()
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 600,
            }
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)
            summary = response.choices[0].message.content.strip()

            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            return summary[:1500]

        except Exception as e:
            print(f"[SUMMARY ERROR] {e}")
            return self._generate_simple_summary(segment_turns)

    async def _generate_concise_summary(self) -> str:
        """Generate a concise summary."""
        segment_turns = [t for t in self.turns if t.segment == self.current_segment]
        if not segment_turns:
            return "No prior discussion."

        agent_turns = [t for t in segment_turns if t.agent_name != "Orchestrator"][-10:]
        discussion_text = "\n".join([
            f"{t.agent_name}: {t.content[:400]}"
            for t in agent_turns
        ])

        prompt = f"""Extract the 3-5 most important insights from this discussion.

Discussion:
{discussion_text}

Brief bullet-point summary (max 500 chars):"""

        try:
            model = self._get_orchestrator_model()
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 200,
            }
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)
            return response.choices[0].message.content.strip()[:500]

        except Exception:
            return self._generate_simple_summary(agent_turns)

    def _generate_simple_summary(self, turns: list[DiscussionTurn]) -> str:
        """Generate a simple summary without LLM."""
        key_points = []
        for t in turns[-5:]:
            content = t.content[:150]
            key_points.append(f"- {t.agent_name}: {content}...")
        return "Key Points:\n" + "\n".join(key_points)[:500]

    async def _orchestrator_interjection(self, progress_callback=None):
        """Orchestrator steps in to guide the discussion."""
        recent = self.turns[-self.config.orchestrator_frequency:]
        discussion_text = "\n".join([f"{t.agent_name}: {t.content}" for t in recent])

        prompt = f"""As the discussion facilitator, analyze the recent conversation:

Recent discussion:
{discussion_text}

Your role:
1. Summarize the key points made
2. Identify emerging consensus or disagreements
3. Ask a probing question to deepen the discussion
4. Keep the group focused on the topic: {self.config.topic}

Be concise but helpful."""

        try:
            model = self._get_orchestrator_model()
            completion_kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": get_persona("the_orchestrator").system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.5,
                "max_tokens": 400,
            }
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)
            message = response.choices[0].message.content

            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            turn = DiscussionTurn(
                turn_number=self.current_turn + 0.5,
                agent_name="Orchestrator",
                persona="Manager",
                content=message,
                segment=self.current_segment,
            )
            self.turns.append(turn)

            for agent in self.agents:
                agent.add_message("user", f"Orchestrator: {message}")

            if progress_callback:
                await progress_callback("orchestrator", message)

            # Also save key insights to file and database
            await self._save_key_insights(progress_callback)

        except Exception as e:
            print(f"[ORCHESTRATOR ERROR] {e}")

    async def _save_key_insights(self, progress_callback=None):
        """Generate and save key insights to file and database."""
        print(f"[KEY INSIGHTS DEBUG] Starting _save_key_insights, session_id={self.config.session_id}, turn={self.current_turn}")

        if not self.config.session_id:
            print("[KEY INSIGHTS DEBUG] No session_id, skipping")
            return

        # Get non-orchestrator turns from current segment
        segment_turns = [t for t in self.turns if t.segment == self.current_segment and t.agent_name != "Orchestrator"]
        print(f"[KEY INSIGHTS DEBUG] Found {len(segment_turns)} non-orchestrator turns in segment {self.current_segment}")
        if len(segment_turns) < 3:
            print(f"[KEY INSIGHTS DEBUG] Not enough turns (< 3), skipping")
            return

        # Filter out error messages, tool debug info, and non-substantive content
        def is_substantive_content(content: str) -> bool:
            """Check if content contains actual discussion insights, not errors/debug."""
            content_lower = content.lower().strip()

            # Skip error messages about tools
            if content_lower.startswith("[error:") or "tool rejected" in content_lower:
                return False
            if "invoking" in content_lower and "incorrect parameter" in content_lower:
                return False
            if content_lower.startswith("the tool rejects"):
                return False
            if "suggesting the actual parameter" in content_lower:
                return False

            # Skip very short messages
            if len(content) < 30:
                return False

            # Skip messages that are just about tool execution
            if content_lower.startswith("["):
                return False

            return True

        # Filter turns to only include substantive discussion
        substantive_turns = [t for t in segment_turns if is_substantive_content(t.content)]
        print(f"[KEY INSIGHTS DEBUG] Found {len(substantive_turns)} substantive turns after filtering")

        if len(substantive_turns) < 2:
            print(f"[KEY INSIGHTS DEBUG] Not enough substantive turns after filtering, skipping")
            return

        # Get recent discussion
        recent_turns = substantive_turns[-10:]
        discussion_text = "\n".join([f"{t.agent_name}: {t.content[:500]}" for t in recent_turns])

        prompt = f"""You are an expert at extracting key insights from discussions.

Analyze this discussion segment and identify 3-5 key insights worth preserving:

{discussion_text}

To save these insights, you MUST use the save_insights tool with this exact format:

{{"tool_calls": [{{"name": "save_insights", "arguments": {{"insights": ["Insight 1 sentence", "Insight 2 sentence", "Insight 3 sentence"]}}}}]}}

Requirements:
- Extract 3-5 substantive insights, arguments, or findings
- Each insight must be a single clear sentence
- Use ONLY the tool_calls format above, no other text"""

        try:
            model = self._get_orchestrator_model()
            print(f"[KEY INSIGHTS DEBUG] Calling LLM with model: {model}")
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)
            insights_content = response.choices[0].message.content.strip()
            print(f"[KEY INSIGHTS DEBUG] LLM response received: {len(insights_content)} chars")

            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            # Parse using tool_calls format (same as agent tool calls)
            insights_list = []
            try:
                # First try direct JSON parse (if content is clean)
                try:
                    parsed = json.loads(insights_content)
                    if "tool_calls" in parsed:
                        for call in parsed["tool_calls"]:
                            if call.get("name") == "save_insights":
                                insights_list = call.get("arguments", {}).get("insights", [])
                                print(f"[KEY INSIGHTS DEBUG] Found {len(insights_list)} insights via direct JSON parse")
                                break
                except json.JSONDecodeError:
                    pass

                # If no insights yet, try regex extraction
                if not insights_list:
                    tool_calls = self._extract_tool_calls(insights_content)
                    print(f"[KEY INSIGHTS DEBUG] Extracted {len(tool_calls)} tool calls via regex")

                    for call in tool_calls:
                        if call.get("name") == "save_insights":
                            args = call.get("arguments", {})
                            insights_list = args.get("insights", [])
                            print(f"[KEY INSIGHTS DEBUG] Found {len(insights_list)} insights in tool call")
                            break

            except Exception as e:
                print(f"[KEY INSIGHTS DEBUG] Parse error: {e}")

            if not insights_list:
                print(f"[KEY INSIGHTS DEBUG] No insights found, raw content: {insights_content[:1000]}")
                return

            print(f"[KEY INSIGHTS DEBUG] Saving {len(insights_list)} insights to database")

            # Save to database
            insight_numbers = db.save_insights_batch(
                session_id=self.config.session_id,
                insights=insights_list,
                source='orchestrator',
                turn_number=self.current_turn,
                segment=self.current_segment
            )

            # Save to file (markdown format)
            session_folder = os.path.join(self.config.workspace_path, "chats", self.config.session_id)
            os.makedirs(session_folder, exist_ok=True)
            insights_file = os.path.join(session_folder, "key_insights.md")

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(insights_file, "a") as f:
                f.write(f"\n## Key Insights (Turn {self.current_turn}, Segment {self.current_segment + 1}) - {timestamp}\n\n")
                for i, insight in enumerate(insights_list, 1):
                    f.write(f"{i}. {insight}\n")
                f.write("\n---\n")

            print(f"[KEY INSIGHTS] Saved {len(insights_list)} insights to database and {insights_file}")

            # Notify via callback if provided (for WebSocket)
            if progress_callback:
                print(f"[KEY INSIGHTS DEBUG] Sending insights via WebSocket callback")
                from app.models.schemas import KeyInsight
                insight_objects = [
                    KeyInsight(
                        insight_number=num,
                        content=content,
                        source='orchestrator',
                        turn_number=self.current_turn,
                        segment=self.current_segment,
                    )
                    for num, content in zip(insight_numbers, insights_list)
                ]
                await progress_callback("insights", {
                    "insights": insight_objects,
                    "total_count": db.get_insight_count(self.config.session_id)
                })
                print(f"[KEY INSIGHTS DEBUG] WebSocket callback completed")
            else:
                print(f"[KEY INSIGHTS DEBUG] No progress_callback provided!")

        except Exception as e:
            print(f"[KEY INSIGHTS ERROR] {e}")
            import traceback
            traceback.print_exc()

    async def _save_key_insights_for_segment(self, progress_callback=None):
        """Generate and save key insights for the CURRENT segment (called at segment end).

        This method explicitly uses self.current_segment to ensure insights are saved
        for the segment that is ending, not any future segment.
        """
        print(f"[SEGMENT INSIGHTS DEBUG] Starting for segment {self.current_segment}")

        if not self.config.session_id:
            print("[SEGMENT INSIGHTS DEBUG] No session_id, skipping")
            return

        # Get non-orchestrator turns from CURRENT segment (the one ending)
        segment_number = self.current_segment
        segment_turns = [t for t in self.turns if t.segment == segment_number and t.agent_name != "Orchestrator"]
        print(f"[SEGMENT INSIGHTS DEBUG] Found {len(segment_turns)} non-orchestrator turns in segment {segment_number}")

        if len(segment_turns) < 2:
            print(f"[SEGMENT INSIGHTS DEBUG] Not enough turns (< 2), skipping")
            return

        # Filter out error messages, tool debug info, and non-substantive content
        def is_substantive_content(content: str) -> bool:
            content_lower = content.lower().strip()
            if content_lower.startswith("[error:") or "tool rejected" in content_lower:
                return False
            if "invoking" in content_lower and "incorrect parameter" in content_lower:
                return False
            if content_lower.startswith("the tool rejects"):
                return False
            if "suggesting the actual parameter" in content_lower:
                return False
            if len(content) < 30:
                return False
            if content_lower.startswith("["):
                return False
            return True

        substantive_turns = [t for t in segment_turns if is_substantive_content(t.content)]
        print(f"[SEGMENT INSIGHTS DEBUG] Found {len(substantive_turns)} substantive turns after filtering")

        if len(substantive_turns) < 2:
            print(f"[SEGMENT INSIGHTS DEBUG] Not enough substantive turns after filtering, skipping")
            return

        # Get recent discussion from this segment
        recent_turns = substantive_turns[-10:]
        discussion_text = "\n".join([f"{t.agent_name}: {t.content[:500]}" for t in recent_turns])

        prompt = f"""You are an expert at extracting key insights from discussions.

Analyze this discussion segment and identify 3-5 key insights worth preserving:

{discussion_text}

To save these insights, you MUST use the save_insights tool with this exact format:

{{"tool_calls": [{{"name": "save_insights", "arguments": {{"insights": ["Insight 1 sentence", "Insight 2 sentence", "Insight 3 sentence"]}}}}]}}

Requirements:
- Extract 3-5 substantive insights, arguments, or findings
- Each insight must be a single clear sentence
- Use ONLY the tool_calls format above, no other text"""

        try:
            model = self._get_orchestrator_model()
            print(f"[SEGMENT INSIGHTS DEBUG] Calling LLM for segment {segment_number}")
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)
            insights_content = response.choices[0].message.content.strip()
            print(f"[SEGMENT INSIGHTS DEBUG] LLM response: {len(insights_content)} chars")

            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            # Parse insights
            insights_list = []
            try:
                try:
                    parsed = json.loads(insights_content)
                    if "tool_calls" in parsed:
                        for call in parsed["tool_calls"]:
                            if call.get("name") == "save_insights":
                                insights_list = call.get("arguments", {}).get("insights", [])
                                break
                except json.JSONDecodeError:
                    pass

                if not insights_list:
                    tool_calls = self._extract_tool_calls(insights_content)
                    for call in tool_calls:
                        if call.get("name") == "save_insights":
                            args = call.get("arguments", {})
                            insights_list = args.get("insights", [])
                            break
            except Exception as e:
                print(f"[SEGMENT INSIGHTS DEBUG] Parse error: {e}")

            if not insights_list:
                print(f"[SEGMENT INSIGHTS DEBUG] No insights found")
                return

            print(f"[SEGMENT INSIGHTS DEBUG] Saving {len(insights_list)} insights for segment {segment_number}")

            # Save to database with EXPLICIT segment number
            insight_numbers = db.save_insights_batch(
                session_id=self.config.session_id,
                insights=insights_list,
                source='orchestrator',
                turn_number=self.current_turn,
                segment=segment_number  # Explicitly use the segment number
            )

            # Save to file
            session_folder = os.path.join(self.config.workspace_path, "chats", self.config.session_id)
            os.makedirs(session_folder, exist_ok=True)
            insights_file = os.path.join(session_folder, "key_insights.md")

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(insights_file, "a") as f:
                f.write(f"\n## Key Insights (Segment {segment_number + 1} End) - {timestamp}\n\n")
                for i, insight in enumerate(insights_list, 1):
                    f.write(f"{i}. {insight}\n")
                f.write("\n---\n")

            print(f"[SEGMENT INSIGHTS] Saved {len(insights_list)} insights for segment {segment_number}")

            # Notify via callback
            if progress_callback:
                from app.models.schemas import KeyInsight
                insight_objects = [
                    KeyInsight(
                        insight_number=num,
                        content=content,
                        source='orchestrator',
                        turn_number=self.current_turn,
                        segment=segment_number,
                    )
                    for num, content in zip(insight_numbers, insights_list)
                ]
                await progress_callback("insights", {
                    "insights": insight_objects,
                    "total_count": db.get_insight_count(self.config.session_id)
                })

        except Exception as e:
            print(f"[SEGMENT INSIGHTS ERROR] {e}")
            import traceback
            traceback.print_exc()

    async def _generate_summary(self, start_datetime: datetime) -> DiscussionSummary:
        """Generate a comprehensive solutioning document for the discussion."""
        # Build discussion text with segment markers
        discussion_text = ""
        current_segment = 0
        for t in self.turns:
            if t.segment != current_segment:
                current_segment = t.segment
                discussion_text += f"\n\n=== SEGMENT {current_segment} ===\n\n"
            discussion_text += f"{t.agent_name} ({t.persona}): {t.content}\n\n"

        # Build segment summaries
        segment_reports = []
        for seg in self.segments:
            segment_turns = [t for t in self.turns if t.segment == seg.segment_number]
            seg_text = "\n".join([f"{t.agent_name}: {t.content}" for t in segment_turns])

            agent_contributions = {}
            for agent in self.agents:
                agent_turns = [t for t in segment_turns if t.agent_name == agent.config.name]
                if agent_turns:
                    contributions = "; ".join([t.content[:100] + "..." if len(t.content) > 100 else t.content for t in agent_turns[:3]])
                    agent_contributions[agent.config.name] = contributions

            segment_reports.append({
                "segment_number": seg.segment_number,
                "summary": seg.summary or f"Segment {seg.segment_number} discussion",
                "key_developments": [],
                "agent_contributions": agent_contributions,
                "decisions_made": [],
                "open_questions": [],
            })

        # Build fallback content from discussion
        fallback_problem = f"Discussion on: {self.config.topic}"
        fallback_answer = f"The council discussed '{self.config.topic}' across {len(self.segments)} segment(s) with {len(self.turns)} turns. "
        if len(self.turns) > 0:
            key_contributors = list(set([t.agent_name for t in self.turns]))[:5]
            fallback_answer += f"Key contributors: {', '.join(key_contributors)}. "
            # Extract first meaningful contribution as context
            for t in self.turns[:3]:
                if len(t.content) > 50:
                    fallback_answer += f"{t.agent_name} noted: {t.content[:200]}... "
                    break

        prompt = f"""You are creating a comprehensive SOLUTIONING DOCUMENT based on a multi-agent council discussion.

TOPIC: {self.config.topic}

FULL DISCUSSION TRANSCRIPT:
{discussion_text}

Your task is to analyze this discussion and create a detailed solutioning document. Return ONLY a JSON response in this exact format:

{{
    "problem_statement": "Clear, concise statement of the problem/question being addressed - MUST be non-empty, describe what was discussed",
    "key_points": ["Key insight 1", "Key insight 2", ...],
    "consensus_reached": true/false,
    "disagreements": ["Description of disagreement 1", ...],

    "solution_options": [
        {{
            "option_name": "Name of option/solution",
            "description": "Detailed description of this solution approach",
            "pros": ["Advantage 1", "Advantage 2", ...],
            "cons": ["Disadvantage 1", "Disadvantage 2", ...],
            "supporters": ["AgentName1", "AgentName2"],
            "opposers": ["AgentName3"]
        }}
    ],

    "selected_solution": "Name of the selected/best solution option (or null if none selected)",
    "selection_reasoning": "Detailed explanation of why this solution was chosen, including trade-offs considered",

    "agent_analyses": [
        {{
            "agent_name": "Agent Name",
            "persona": "Persona type",
            "critical_points": ["Critical point they raised", ...],
            "key_arguments": ["Their main argument", ...],
            "tools_used": ["tool_name1", ...],
            "stance": "supportive|opposed|neutral|skeptical"
        }}
    ],

    "segment_analyses": [
        {{
            "segment_number": 1,
            "key_developments": ["What happened in this segment"],
            "decisions_made": ["Decisions made"],
            "open_questions": ["Questions raised"]
        }}
    ],

    "final_answer": "Direct, actionable answer to the original question (2-3 paragraphs) - MUST be non-empty, summarize the discussion outcomes",
    "justification": "Comprehensive reasoning for the final answer, addressing key concerns - MUST be non-empty, explain the reasoning process",
    "implementation_steps": ["Step 1: ...", "Step 2: ...", ...],
    "risks_and_mitigations": ["Risk: ... | Mitigation: ...", ...],
    "action_items": ["Specific action item 1", "Action item 2", ...],
    "final_recommendation": "Executive summary recommendation (1 paragraph) - MUST be non-empty"
}}

CRITICAL INSTRUCTIONS:
1. ALL fields marked "MUST be non-empty" must contain meaningful content. Do not return empty strings.
2. Even if no consensus was reached, describe what WAS discussed and the current state of thinking.
3. The problem_statement should describe the topic/question that was addressed.
4. The final_answer should summarize what the council concluded, even if it's "The council explored multiple perspectives but did not reach consensus. Key considerations include..."
5. Include practical implementation steps and real risks with mitigations.
6. Be thorough and specific. Reference agent names and their actual contributions.
7. For agent analyses, capture their unique perspective based on their persona.

FALLBACK CONTENT (use if discussion seems sparse):
- Problem: {fallback_problem}
- Summary: {fallback_answer}"""

        try:
            model = self._get_orchestrator_model()
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 4000,
            }
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)
            content = response.choices[0].message.content

            # Extract JSON
            try:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(content[start:end])
                else:
                    parsed = {}
            except json.JSONDecodeError:
                parsed = {}

            # Merge segment analyses with existing segment reports
            for seg_analysis in parsed.get("segment_analyses", []):
                for seg_report in segment_reports:
                    if seg_report["segment_number"] == seg_analysis.get("segment_number"):
                        seg_report["key_developments"] = seg_analysis.get("key_developments", [])
                        seg_report["decisions_made"] = seg_analysis.get("decisions_made", [])
                        seg_report["open_questions"] = seg_analysis.get("open_questions", [])

            # Ensure critical fields have fallback content
            problem_statement = parsed.get("problem_statement", "")
            if not problem_statement:
                problem_statement = f"The council discussed: {self.config.topic}"

            final_answer = parsed.get("final_answer", "")
            if not final_answer:
                final_answer = fallback_answer

            justification = parsed.get("justification", "")
            if not justification:
                consensus_status = "reached consensus" if parsed.get("consensus_reached") else "explored multiple perspectives"
                justification = f"The council {consensus_status} on '{self.config.topic}'. Key points were: " + "; ".join(parsed.get("key_points", ["No specific points recorded"])[:3])

            final_recommendation = parsed.get("final_recommendation")
            if not final_recommendation:
                final_recommendation = f"Based on the discussion of '{self.config.topic}', the council {('recommends proceeding with: ' + str(parsed.get('selected_solution'))) if parsed.get('selected_solution') else 'suggests further exploration of the topic.'}"

            return DiscussionSummary(
                topic=self.config.topic,
                start_time=start_datetime.isoformat(),
                end_time=datetime.now().isoformat(),
                total_turns=self.current_turn,
                key_points=parsed.get("key_points", []),
                consensus_reached=parsed.get("consensus_reached", False),
                disagreements=parsed.get("disagreements", []),
                action_items=parsed.get("action_items", []),
                problem_statement=problem_statement,
                solution_options=parsed.get("solution_options", []),
                selected_solution=parsed.get("selected_solution"),
                selection_reasoning=parsed.get("selection_reasoning", ""),
                segment_reports=segment_reports,
                agent_analyses=parsed.get("agent_analyses", []),
                final_recommendation=final_recommendation,
                final_answer=final_answer,
                justification=justification,
                implementation_steps=parsed.get("implementation_steps", []),
                risks_and_mitigations=parsed.get("risks_and_mitigations", []),
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return DiscussionSummary(
                topic=self.config.topic,
                start_time=start_datetime.isoformat(),
                end_time=datetime.now().isoformat(),
                total_turns=self.current_turn,
                key_points=[f"Error generating comprehensive summary: {str(e)}"],
                consensus_reached=False,
                disagreements=[],
                action_items=[],
                final_recommendation="Summary generation encountered an error. Please review the discussion transcript directly.",
            )

    def _get_orchestrator_model(self) -> str:
        """Get the orchestrator model name."""
        if self.config.litellm_proxy and not self.config.orchestrator_model.startswith("openai/"):
            return f"openai/{self.config.orchestrator_model}"
        return self.config.orchestrator_model

    def _extract_tool_calls(self, content: str) -> list[dict]:
        """Extract tool calls from response content (same as agent)."""
        tool_calls = []
        try:
            # Try to find the full JSON object with tool_calls
            # Use DOTALL to match across newlines
            pattern = r'\{\s*"tool_calls"\s*:\s*\[.*?\]\s*\}'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if "tool_calls" in parsed and isinstance(parsed["tool_calls"], list):
                    tool_calls = parsed["tool_calls"]
                    print(f"[KEY INSIGHTS DEBUG] Found {len(tool_calls)} tool calls in content")
            else:
                print(f"[KEY INSIGHTS DEBUG] No tool_calls pattern match in content: {content[:200]}...")
        except json.JSONDecodeError as e:
            print(f"[KEY INSIGHTS DEBUG] JSON parse error: {e}, content: {content[:200]}...")
        except re.error as e:
            print(f"[KEY INSIGHTS DEBUG] Regex error: {e}")
        return tool_calls

    def _save_transcript(self):
        """Save the discussion transcript."""
        if not self.config.session_id:
            self.config.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        session_folder = os.path.join(self.config.workspace_path, "chats", self.config.session_id)
        os.makedirs(session_folder, exist_ok=True)

        filename = os.path.join(session_folder, f"transcript_{self.config.session_id}.json")

        transcript = {
            "topic": self.config.topic,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            "end_time": datetime.now().isoformat(),
            "total_turns": self.current_turn,
            "total_tokens": self.total_tokens_used,
            "current_segment": self.current_segment,
            "agents": [{"name": a.config.name, "model": a.config.model, "persona": a.config.persona} for a in self.agents],
            "segments": [
                {
                    "segment_number": s.segment_number,
                    "start_turn": s.start_turn,
                    "end_turn": s.end_turn,
                    "summary": s.summary,
                    "orchestrator_message": s.orchestrator_message,
                }
                for s in self.segments
            ],
            "turns": [
                {
                    "turn_number": t.turn_number,
                    "agent": t.agent_name,
                    "persona": t.persona,
                    "content": t.content,
                    "timestamp": datetime.fromtimestamp(t.timestamp).isoformat(),
                    "tool_calls": t.tool_calls,
                    "tool_results": t.tool_results,
                    "segment": t.segment,
                }
                for t in self.turns
            ],
        }

        with open(filename, "w") as f:
            json.dump(transcript, f, indent=2)

        return filename

    def add_user_message(self, content: str):
        """Add a user message to the discussion."""
        turn = DiscussionTurn(
            turn_number=self.current_turn + 0.1,
            agent_name="You",
            persona="Human",
            content=content,
            segment=self.current_segment,
        )
        self.turns.append(turn)

        for agent in self.agents:
            agent.add_message("user", f"User: {content}")
