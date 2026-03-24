"""Orchestrator for managing council discussions."""

import asyncio
import json
import os
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
        self.tool_server = MCPToolServer(config.workspace_path)
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
        """Initialize all council agents."""
        for agent_config in self.config.agents:
            agent = CouncilAgent(
                config=agent_config,
                tool_server=self.tool_server,
                litellm_proxy=self.config.litellm_proxy,
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
        summary = await self._generate_summary(start_datetime)

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

        # Get recent discussion
        recent_turns = segment_turns[-10:]
        discussion_text = "\n".join([f"{t.agent_name}: {t.content[:500]}" for t in recent_turns])

        prompt = f"""You are an expert at extracting key insights from discussions.

Analyze this discussion segment and identify 3-5 key insights worth preserving:

{discussion_text}

Requirements:
- Extract only substantive insights, arguments, or findings
- Each insight must be a single clear sentence
- Return ONLY valid JSON, no markdown, no explanations

Your response must be ONLY this JSON format:
{{"insights": ["First insight here", "Second insight here", "Third insight here"]}}"""

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

            # Parse JSON response - try multiple approaches
            insights_list = []
            try:
                import re
                # Try to find JSON object with insights key
                json_match = re.search(r'\{[^}]*"insights"[^}]*\}', insights_content, re.DOTALL)
                print(f"[KEY INSIGHTS DEBUG] JSON regex match: {json_match is not None}")

                if json_match:
                    parsed = json.loads(json_match.group(0))
                    insights_list = parsed.get("insights", [])
                else:
                    # Try to parse entire response as JSON
                    parsed = json.loads(insights_content)
                    insights_list = parsed.get("insights", [])

                print(f"[KEY INSIGHTS DEBUG] Parsed insights count: {len(insights_list)}")
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"[KEY INSIGHTS DEBUG] JSON parse error: {e}, using fallback")
                # Fallback: extract lines that look like insights (bullet points or quoted strings)
                lines = insights_content.split('\n')
                for line in lines:
                    line = line.strip()
                    # Look for bullet points, numbers, or quoted strings
                    if line and not line.startswith('{') and not line.startswith('}'):
                        # Remove common prefixes
                        line = re.sub(r'^[-*•\d.\)\]]+\s*', '', line)
                        # Remove quotes
                        line = line.strip('"\'')
                        if line and len(line) > 20:  # Must be substantial
                            insights_list.append(line)
                print(f"[KEY INSIGHTS DEBUG] Fallback extracted {len(insights_list)} insights")

            if not insights_list:
                print(f"[KEY INSIGHTS DEBUG] No insights found in response, raw content: {insights_content[:500]}")
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

    async def _generate_summary(self, start_datetime: datetime) -> DiscussionSummary:
        """Generate a summary of the discussion."""
        discussion_text = "\n".join([f"{t.agent_name}: {t.content}" for t in self.turns])

        prompt = f"""Analyze this council discussion and provide a structured summary:

Topic: {self.config.topic}

Discussion:
{discussion_text}

Provide a JSON response with:
{{
    "key_points": ["point 1", ...],
    "consensus_reached": true/false,
    "disagreements": ["disagreement 1", ...],
    "action_items": ["action 1", ...],
    "final_recommendation": "Overall recommendation"
}}"""

        try:
            model = self._get_orchestrator_model()
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000,
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

            return DiscussionSummary(
                topic=self.config.topic,
                start_time=start_datetime.isoformat(),
                end_time=datetime.now().isoformat(),
                total_turns=self.current_turn,
                key_points=parsed.get("key_points", []),
                consensus_reached=parsed.get("consensus_reached", False),
                disagreements=parsed.get("disagreements", []),
                action_items=parsed.get("action_items", []),
                final_recommendation=parsed.get("final_recommendation"),
            )

        except Exception as e:
            return DiscussionSummary(
                topic=self.config.topic,
                start_time=start_datetime.isoformat(),
                end_time=datetime.now().isoformat(),
                total_turns=self.current_turn,
                key_points=["Error generating summary"],
                consensus_reached=False,
                disagreements=[],
                action_items=[],
                final_recommendation=f"Summary generation failed: {e}",
            )

    def _get_orchestrator_model(self) -> str:
        """Get the orchestrator model name."""
        if self.config.litellm_proxy and not self.config.orchestrator_model.startswith("openai/"):
            return f"openai/{self.config.orchestrator_model}"
        return self.config.orchestrator_model

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
