"""Orchestrator that manages the council discussion."""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from litellm import completion, token_counter

from .agent import AgentConfig, CouncilAgent
from .config import CouncilConfig
from .personas import get_persona
from .tools import ToolRegistry


@dataclass
class DiscussionTurn:
    """A single turn in the discussion."""

    turn_number: int
    agent_name: str
    persona: str
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_calls: list = field(default_factory=list)
    tool_results: list = field(default_factory=list)
    segment: int = 0  # Which segment this turn belongs to


@dataclass
class DiscussionSegment:
    """A segment of the discussion (like a sub-tab)."""

    segment_number: int
    start_turn: int
    end_turn: Optional[int] = None
    summary: str = ""  # Summary of prior discussion
    orchestrator_message: str = ""  # The transition message


@dataclass
class DiscussionSummary:
    """Summary of a completed discussion."""

    topic: str
    start_time: datetime
    end_time: datetime
    total_turns: int
    key_points: list[str]
    consensus_reached: bool
    disagreements: list[str]
    action_items: list[str]
    final_recommendation: Optional[str] = None


class CouncilOrchestrator:
    """Orchestrates the agent council discussion."""

    def __init__(self, config: CouncilConfig):
        self.config = config
        self.tool_registry = ToolRegistry(config.workspace_path)
        self.agents: list[CouncilAgent] = []
        self.turns: list[DiscussionTurn] = []
        self.segments: list[DiscussionSegment] = []
        self.start_time: Optional[float] = None
        self.current_turn = 0
        self.total_tokens_used: int = 0
        self.current_segment = 0
        self._pending_segment_transition = False
        self._setup_agents()
        # Initialize first segment
        self.segments.append(DiscussionSegment(
            segment_number=0,
            start_turn=1,
            summary="",
            orchestrator_message=""
        ))

    def _setup_agents(self):
        """Initialize all council agents."""
        for agent_config in self.config.agents:
            persona = get_persona(agent_config.persona)
            agent = CouncilAgent(
                agent_config,
                persona,
                self.tool_registry,
                litellm_proxy=self.config.litellm_proxy,
            )
            self.agents.append(agent)

    async def run_discussion(self, progress_callback=None) -> DiscussionSummary:
        """
        Run the full council discussion.

        Args:
            progress_callback: Optional callback(current_turn, total_turns, turn_data)

        Returns:
            DiscussionSummary with results
        """
        self.start_time = time.time()
        start_datetime = datetime.now()

        # Initial topic presentation
        initial_context = f"""Welcome to the Council Discussion.

TOPIC: {self.config.topic}

This is a deliberative discussion to thoroughly explore this topic. You are all expert advisors with different perspectives.

Guidelines:
- Engage authentically as your persona
- Listen to others and respond to their points
- Use tools when you need information
- Aim for depth over speed

Let's begin. Each of you will have a chance to share your initial thoughts."""

        # Notify all agents of the topic
        for agent in self.agents:
            agent.add_message("user", initial_context)

        # Run discussion loop
        while self._should_continue():
            self.current_turn += 1

            # Select next speaker
            speaker = self._select_next_speaker()
            if not speaker:
                break

            # Build context for this turn
            context = self._build_context_for_agent(speaker)

            # Get response from agent
            response = await speaker.think_and_respond(context)

            # Track token usage
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

            # Extract and save insights from this response
            await self._extract_and_save_insights(turn)

            # Broadcast to all other agents
            self._broadcast_turn(turn)

            # Progress callback
            if progress_callback:
                await progress_callback(self.current_turn, self.config.max_turns, turn)

            # Check if we need to start a new segment (context overflow)
            await self._check_and_start_new_segment()

            # Orchestrator interjection
            if self.current_turn % self.config.orchestrator_frequency == 0:
                await self._orchestrator_interjection()

        # Generate summary
        summary = await self._generate_summary(start_datetime)

        # Save transcript if enabled
        if self.config.save_transcript:
            self._save_transcript()

        return summary

    def _should_continue(self) -> bool:
        """Determine if discussion should continue."""
        if self.start_time is None:
            return True

        elapsed = time.time() - self.start_time
        elapsed_minutes = elapsed / 60

        # Check time limit
        if elapsed_minutes >= self.config.max_duration_minutes:
            return False

        # Check min/max turns
        if self.current_turn < self.config.min_turns:
            return True
        if self.current_turn >= self.config.max_turns:
            return False

        return True

    async def _check_and_start_new_segment(self, allow_transition: bool = True) -> bool:
        """
        Check if any agent's context exceeds the threshold and start a new segment if needed.

        Args:
            allow_transition: If False, only check but don't transition (used during tool calls)

        When triggered, this will:
        1. Close the current segment
        2. Generate a summary of prior discussion
        3. Create a new segment with orchestrator transition message
        4. Reset all agents with fresh context

        Returns:
            True if new segment was started, False otherwise
        """
        threshold = self.config.context_compression_threshold

        # Find agents that need new segment
        agents_needing_reset = [
            agent for agent in self.agents
            if len(agent.messages) >= threshold
        ]

        if not agents_needing_reset:
            return False

        # If we're in the middle of a turn (tool calls), queue the transition for next turn
        if not allow_transition:
            print(f"[SEGMENT TRANSITION] {len(agents_needing_reset)} agent(s) exceeded {threshold} messages. Will transition after current turn completes.")
            self._pending_segment_transition = True
            return False

        print(f"[SEGMENT TRANSITION] {len(agents_needing_reset)} agent(s) exceeded {threshold} messages. Starting new segment...")

        # Start new segment
        await self._start_new_segment()
        self._pending_segment_transition = False

        return True

    async def _start_new_segment(self):
        """
        Start a new discussion segment.

        This generates a detailed summary, closes the current segment, and creates
        a fresh start for all agents with an orchestrator transition message.
        """
        # Generate detailed summary of current segment for orchestrator
        detailed_summary = await self._generate_detailed_segment_summary()

        # Generate concise summary for key insights file
        concise_summary = await self._generate_concise_summary()

        # Close current segment
        current_seg = self.segments[self.current_segment]
        current_seg.end_turn = self.current_turn
        current_seg.summary = concise_summary

        # Create orchestrator transition message with detailed summary
        transition_message = self._generate_transition_message(detailed_summary)
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

        print(f"[SEGMENT TRANSITION] Starting segment {self.current_segment} at turn {self.current_turn + 1}")

        # Reset all agents with fresh context starting with orchestrator message
        for agent in self.agents:
            self._reset_agent_for_new_segment(agent, transition_message)

        # Add transition as a turn in the new segment
        turn = DiscussionTurn(
            turn_number=self.current_turn + 0.5,  # Decimal to show it's interstitial
            agent_name="Orchestrator",
            persona="Manager",
            content=transition_message,
            segment=self.current_segment,
        )
        self.turns.append(turn)

        print(f"[SEGMENT TRANSITION] All agents reset for new segment {self.current_segment}")

    def _reset_agent_for_new_segment(self, agent: CouncilAgent, transition_message: str):
        """
        Reset an agent's message history for a new segment.

        Keeps only the system message, adds the original topic, and adds the transition message as context.
        """
        from .agent import AgentMessage

        # Keep only system message
        system_message = None
        for msg in agent.messages:
            if msg.role == "system":
                system_message = msg
                break

        # Build fresh message list
        new_messages = []
        if system_message:
            new_messages.append(system_message)

        # Add original topic as context
        new_messages.append(AgentMessage(
            role="user",
            content=f"Original Topic: {self.config.topic}",
            agent_name="User"
        ))

        # Add transition message as user message
        new_messages.append(AgentMessage(
            role="user",
            content=transition_message,
            agent_name="Orchestrator"
        ))

        # Replace agent's messages
        old_count = len(agent.messages)
        agent.messages = new_messages

        print(f"[SEGMENT TRANSITION] {agent.config.name} reset: {old_count} -> {len(agent.messages)} messages")

    async def _generate_detailed_segment_summary(self) -> str:
        """Generate a detailed summary for the orchestrator transition message."""
        # Get all turns in current segment
        segment_turns = [t for t in self.turns if t.segment == self.current_segment]

        if not segment_turns:
            return "No prior discussion."

        # Build discussion text
        discussion_text = "\n\n".join([
            f"{t.agent_name}: {t.content[:800]}"
            for t in segment_turns[-15:]  # Last 15 turns
        ])

        prompt = f"""Provide a comprehensive summary of this council discussion segment. Structure your response:

**Key Arguments Made:**
- List the main points each agent contributed

**Points of Consensus:**
- What did agents agree on?

**Open Questions / Disagreements:**
- What remains unresolved?

**Critical Insights:**
- Most important facts or perspectives shared

Discussion:
{discussion_text}

Provide a detailed summary (max 1500 characters):"""

        try:
            # Determine model format for LiteLLM proxy
            if (
                self.config.litellm_proxy
                and not self.config.orchestrator_model.startswith("openai/")
            ):
                model = f"openai/{self.config.orchestrator_model}"
            else:
                model = self.config.orchestrator_model

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

            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            summary = response.choices[0].message.content.strip()

            # Enforce max length
            if len(summary) > 1500:
                summary = summary[:1497] + "..."

            return summary

        except Exception as e:
            print(f"[CONTEXT COMPRESSION] Failed to generate detailed summary: {e}")
            # Fallback: create a simple summary from turns
            return self._generate_simple_summary(segment_turns)

    async def _generate_concise_summary(self) -> str:
        """Generate a concise summary for key insights file."""
        # Get all turns in current segment
        segment_turns = [t for t in self.turns if t.segment == self.current_segment]

        if not segment_turns:
            return "No prior discussion."

        # Build discussion text (only agent responses, skip orchestrator)
        agent_turns = [t for t in segment_turns if t.agent_name != "Orchestrator"][-10:]
        discussion_text = "\n".join([
            f"{t.agent_name}: {t.content[:400]}"
            for t in agent_turns
        ])

        prompt = f"""Extract only the 3-5 most important insights from this discussion. Be extremely concise.

Discussion:
{discussion_text}

Provide a brief bullet-point summary (max 500 characters, focus only on critical insights):"""

        try:
            # Determine model format for LiteLLM proxy
            if (
                self.config.litellm_proxy
                and not self.config.orchestrator_model.startswith("openai/")
            ):
                model = f"openai/{self.config.orchestrator_model}"
            else:
                model = self.config.orchestrator_model

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

            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            summary = response.choices[0].message.content.strip()

            # Enforce max length
            if len(summary) > 500:
                summary = summary[:497] + "..."

            return summary

        except Exception as e:
            print(f"[CONTEXT COMPRESSION] Failed to generate concise summary: {e}")
            return self._generate_simple_summary(agent_turns)

    def _generate_simple_summary(self, turns: list[DiscussionTurn]) -> str:
        """Generate a simple summary without LLM call (fallback)."""
        key_points = []
        for t in turns[-5:]:  # Last 5 turns only
            content = t.content[:150]
            key_points.append(f"- {t.agent_name}: {content}...")

        summary = "Key Points:\n" + "\n".join(key_points)

        # Truncate if too long
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return summary

    def _generate_transition_message(self, summary: str) -> str:
        """
        Generate a concise transition message for a new segment.

        This is a lightweight summary - key insights are saved to file.
        """
        # Simple, concise transition without another LLM call
        return f"""[SEGMENT {self.current_segment + 1} - CONTINUED DISCUSSION]

**Original Topic:** {self.config.topic}

**What We've Covered:**
{summary[:800]}...

**Key Insights File:** Check `key_insights.md` in the session folder for detailed findings.

Continue the discussion from here, building on prior points while staying true to your persona."""

    def _select_next_speaker(self) -> Optional[CouncilAgent]:
        """Select which agent speaks next."""
        # Filter agents who should speak based on probability
        willing_agents = [a for a in self.agents if a.should_speak()]

        if not willing_agents:
            willing_agents = self.agents

        # Round-robin with randomness: prefer agents who haven't spoken recently
        last_speakers = [t.agent_name for t in self.turns[-len(self.agents) :]]

        candidates = []
        for agent in willing_agents:
            # Lower score = more likely to speak
            recent_speaks = last_speakers.count(agent.config.name)
            candidates.append((agent, recent_speaks))

        # Sort by recent speaks (ascending)
        candidates.sort(key=lambda x: x[1])

        # Pick from top candidates with some randomness
        top_candidates = candidates[: max(1, len(candidates) // 2)]
        import random

        return random.choice(top_candidates)[0]

    def _build_context_for_agent(self, agent: CouncilAgent) -> str:
        """Build context string for an agent's turn."""
        if not self.turns:
            return "Please share your initial thoughts on the topic."

        # Get recent turns
        recent_turns = self.turns[-3:] if len(self.turns) >= 3 else self.turns

        context_parts = []
        for turn in recent_turns:
            context_parts.append(f"{turn.agent_name} ({turn.persona}): {turn.content}")

        context_parts.append(
            f"\nIt's your turn, {agent.config.name}. Respond to the discussion so far."
        )

        return "\n\n".join(context_parts)

    def _broadcast_turn(self, turn: DiscussionTurn):
        """Broadcast a turn to all agents. their history."""
        message = f"{turn.agent_name} ({turn.persona}): {turn.content}"

        for agent in self.agents:
            if agent.config.name != turn.agent_name:
                agent.add_message("user", message)

    async def _orchestrator_interjection(self):
        """Orchestrator steps in to summarize and guide, writing key insights to file."""
        import json
        import re

        # Get recent discussion
        recent = self.turns[-self.config.orchestrator_frequency :]
        discussion_text = "\n".join([f"{t.agent_name}: {t.content}" for t in recent])

        # Build dynamic guidance based on discussion state
        convergence_instruction = ""
        if len(self.turns) >= 20:
            turns_remaining = self.config.max_turns - self.current_turn
            convergence_instruction = f"""

IMPORTANT: The discussion has reached {len(self.turns)} turns with approximately {turns_remaining} turns remaining. 
It is now time to CONVERGE toward a conclusion.
- Summarize the key agreements and disagreements
- Guide agents toward synthesizing their perspectives
- Encourage them to move toward actionable conclusions or a final consensus
- Remind them that we need to wrap up soon"""

        # Check for topic deviation in recent turns
        deviation_prompt = f"""

Additionally, analyze if the recent discussion has deviated from the main topic: "{self.config.topic}"
If agents are going off-topic, clearly redirect them back to the main discussion."""

        prompt = f"""As the discussion facilitator, analyze the recent conversation and provide guidance:

Recent discussion:
{discussion_text}

Your role:
1. Summarize the key points made
2. Identify any emerging consensus or important disagreements
3. Ask a probing question to deepen the discussion (or push toward convergence if near end)
4. Call out any agent who made a particularly valuable insight
5. Keep the group focused on the topic: {self.config.topic}
6. If the conversation has gone off-topic, redirect everyone back to the main topic{convergence_instruction}{deviation_prompt}

Be concise but helpful. Speak as the Orchestrator."""

        # Prompt to identify key insights worth saving (only critical ones)
        insights_prompt = f"""Analyze this discussion and extract ONLY critical insights that future segments must know.

Include ONLY:
- Novel research findings with specific citations
- Major architectural decisions or trade-offs
- Critical disagreements that affect the direction
- Consensus on core requirements

Discussion:
{discussion_text}

Return JSON with ONLY essential insights (max 2, be extremely selective):
Format: {{"insights": ["insight"]}} or {{"insights": []}} if nothing critical"""

        try:
            # Determine model format for LiteLLM proxy
            if (
                self.config.litellm_proxy
                and not self.config.orchestrator_model.startswith("openai/")
            ):
                model = f"openai/{self.config.orchestrator_model}"
            else:
                model = self.config.orchestrator_model

            # Build completion kwargs
            completion_kwargs = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": get_persona("the_orchestrator").system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.5,
                "max_tokens": 400,
            }

            # Add LiteLLM proxy settings if configured
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)

            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            orchestrator_message = response.choices[0].message.content

            # Add as a turn
            turn = DiscussionTurn(
                turn_number=self.current_turn
                + 0.5,  # Decimal to show it's interstitial
                agent_name="Orchestrator",
                persona="Manager",
                content=orchestrator_message,
                segment=self.current_segment,
            )
            self.turns.append(turn)

            # Broadcast to agents
            for agent in self.agents:
                agent.add_message("user", f"Orchestrator: {orchestrator_message}")

            # Also identify and save key insights
            try:
                insights_kwargs = {
                    "model": model,
                    "messages": [{"role": "user", "content": insights_prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1500,  # Increased to support insights >512 words
                }
                if self.config.litellm_proxy:
                    insights_kwargs["api_base"] = self.config.litellm_proxy.api_base
                    insights_kwargs["api_key"] = self.config.litellm_proxy.api_key

                insights_response = completion(**insights_kwargs)

                # Track token usage
                if hasattr(insights_response, 'usage') and insights_response.usage:
                    self.total_tokens_used += insights_response.usage.total_tokens

                insights_content = insights_response.choices[0].message.content

                # Parse JSON
                json_match = re.search(
                    r'\{[\s\S]*?"insights"[\s\S]*?\}', insights_content
                )
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    insights = parsed.get("insights", [])

                    # Write to file
                    if insights:
                        session_folder = self._get_session_folder()
                        insights_file = os.path.join(session_folder, "key_insights.md")
                        timestamp = datetime.now().strftime("%H:%M:%S")

                        with open(insights_file, "a", encoding="utf-8") as f:
                            f.write(
                                f"\n## Insights from Turn {self.current_turn} ({timestamp})\n\n"
                            )
                            for i, insight in enumerate(insights, 1):
                                f.write(f"{i}. {insight}\n")
                            f.write("\n---\n")

                        print(
                            f"[ORCHESTRATOR] Saved {len(insights)} insights to {insights_file}"
                        )

                        # Notify agents about the file
                        for agent in self.agents:
                            agent.add_message(
                                "user",
                                f"[Orchestrator has saved key insights to {insights_file} - agents can read this file for important context]",
                            )
            except Exception as e:
                print(f"[ORCHESTRATOR] Failed to save insights: {e}")

        except Exception as e:
            print(f"Orchestrator error: {e}")

    def _get_session_folder(self) -> str:
        """Get or create the session folder for storing files."""
        if self.config.session_id:
            folder_name = self.config.session_id
        else:
            folder_name = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.config.session_id = folder_name

        # Store all sessions under a 'chats' folder
        base_folder = os.path.join(self.config.workspace_path, "chats")
        session_folder = os.path.join(base_folder, folder_name)
        os.makedirs(session_folder, exist_ok=True)
        return session_folder

    async def _extract_and_save_insights(self, turn: DiscussionTurn):
        """Extract and save only high-value insights from a single turn."""
        import json
        import re

        # Skip orchestrator's own messages and very short responses
        if turn.agent_name == "Orchestrator" or len(turn.content) < 200:
            return

        # Only extract insights from every 3rd turn to reduce noise
        if turn.turn_number % 3 != 0:
            return

        insights_prompt = f"""Extract ONLY critical insights from this response that would be valuable for future segments to know.

Criteria for inclusion:
- Novel facts or research findings with citations
- Important architectural decisions or trade-offs
- Consensus points that future agents should know
- Critical disagreements that shaped the discussion

Agent: {turn.agent_name} ({turn.persona})
Content: {turn.content[:1500]}

Return JSON with ONLY high-value insights (max 2, be very selective):
Format: {{"insights": ["insight 1"]}} or {{"insights": []}} if nothing truly critical"""

        try:
            # Determine model format for LiteLLM proxy
            if (
                self.config.litellm_proxy
                and not self.config.orchestrator_model.startswith("openai/")
            ):
                model = f"openai/{self.config.orchestrator_model}"
            else:
                model = self.config.orchestrator_model

            # Build completion kwargs
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": insights_prompt}],
                "temperature": 0.3,
                "max_tokens": 200,
            }

            # Add LiteLLM proxy settings if configured
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)

            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens_used += response.usage.total_tokens

            insights_content = response.choices[0].message.content

            # Parse JSON
            json_match = re.search(r'\{[\s\S]*?"insights"[\s\S]*?\}', insights_content)
            if json_match:
                parsed = json.loads(json_match.group(0))
                insights = parsed.get("insights", [])

                # Write to file
                if insights:
                    session_folder = self._get_session_folder()
                    insights_file = os.path.join(session_folder, "key_insights.md")
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    with open(insights_file, "a", encoding="utf-8") as f:
                        f.write(
                            f"\n## {turn.agent_name} - Turn {turn.turn_number} ({timestamp})\n\n"
                        )
                        for i, insight in enumerate(insights, 1):
                            f.write(f"{i}. {insight}\n")
                        f.write("\n---\n")

        except Exception as e:
            # Silently fail for individual turn insights
            pass

    async def _generate_summary(self, start_datetime: datetime) -> DiscussionSummary:
        """Generate a summary of the discussion."""
        discussion_text = "\n".join(
            [f"{t.agent_name}: {t.content}" for t in self.turns]
        )

        prompt = f"""Analyze this council discussion and provide a structured summary:

Topic: {self.config.topic}

Discussion transcript:
{discussion_text}

Provide a JSON response with this structure:
{{
    "key_points": ["point 1", "point 2", ...],
    "consensus_reached": true/false,
    "disagreements": ["disagreement 1", ...],
    "action_items": ["action 1", ...],
    "final_recommendation": "Overall recommendation or conclusion"
}}

Be objective and thorough."""

        try:
            # Determine model format for LiteLLM proxy
            if (
                self.config.litellm_proxy
                and not self.config.orchestrator_model.startswith("openai/")
            ):
                model = f"openai/{self.config.orchestrator_model}"
            else:
                model = self.config.orchestrator_model

            # Build completion kwargs
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000,
            }

            # Add LiteLLM proxy settings if configured
            if self.config.litellm_proxy:
                completion_kwargs["api_base"] = self.config.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.config.litellm_proxy.api_key

            response = completion(**completion_kwargs)

            content = response.choices[0].message.content

            # Extract JSON
            try:
                # Find JSON in response
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    parsed = json.loads(json_str)
                else:
                    parsed = {}
            except json.JSONDecodeError:
                parsed = {}

            return DiscussionSummary(
                topic=self.config.topic,
                start_time=start_datetime,
                end_time=datetime.now(),
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
                start_time=start_datetime,
                end_time=datetime.now(),
                total_turns=self.current_turn,
                key_points=["Error generating summary"],
                consensus_reached=False,
                disagreements=[],
                action_items=[],
                final_recommendation=f"Summary generation failed: {e}",
            )

    def _generate_summary_sync(self) -> DiscussionSummary:
        """Synchronous wrapper for generate_summary."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        start_datetime = (
            datetime.fromtimestamp(self.start_time)
            if self.start_time
            else datetime.now()
        )

        # Create a simple summary from turns
        key_points = []
        for turn in self.turns[-10:]:  # Last 10 turns
            if turn.content and len(turn.content) > 20:
                key_points.append(f"{turn.agent_name}: {turn.content[:100]}...")

        return DiscussionSummary(
            topic=self.config.topic,
            start_time=start_datetime,
            end_time=datetime.now(),
            total_turns=self.current_turn,
            key_points=key_points[:5] if key_points else ["Discussion completed"],
            consensus_reached=False,
            disagreements=[],
            action_items=[],
            final_recommendation="See transcript for full details",
        )

    def _save_transcript(self):
        """Save the discussion transcript to a file in the session folder."""
        # Get or create session folder
        session_folder = self._get_session_folder()

        if not self.config.transcript_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(
                session_folder, f"council_transcript_{timestamp}.json"
            )
        else:
            # If a custom path is provided, use it as-is (user can specify full path)
            filename = self.config.transcript_path

        transcript = {
            "topic": self.config.topic,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat()
            if self.start_time
            else None,
            "end_time": datetime.now().isoformat(),
            "total_turns": self.current_turn,
            "agents": [
                {
                    "name": a.config.name,
                    "model": a.config.model,
                    "persona": a.config.persona,
                }
                for a in self.agents
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
                }
                for t in self.turns
            ],
        }

        with open(filename, "w") as f:
            json.dump(transcript, f, indent=2)

        return filename

    def get_transcript(self) -> list[DiscussionTurn]:
        """Get the full discussion transcript."""
        return self.turns
