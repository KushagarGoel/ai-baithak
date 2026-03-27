"""Service for generating comprehensive discussion reports."""

import json
from datetime import datetime
from typing import Optional
from litellm import completion

from app.core.database import db
from app.models.schemas import DiscussionSummary, DiscussionTurn, DiscussionSegment


class ReportService:
    """Service for generating and managing discussion reports."""

    def __init__(self, litellm_proxy=None):
        self.litellm_proxy = litellm_proxy

    def _get_model_name(self, config_data: dict) -> str:
        """Get properly formatted model name using same logic as agent."""
        # Get model from config or use default
        orchestrator_model = config_data.get('orchestrator_model', 'openai/gpt-4o-mini')

        # Use self.litellm_proxy (same as agent.py lines 125-128)
        if self.litellm_proxy and not orchestrator_model.startswith("openai/"):
            return f"openai/{orchestrator_model}"
        return orchestrator_model

    async def generate_report(
        self,
        session_id: str,
        custom_instructions: Optional[str] = None,
        model: Optional[str] = None
    ) -> DiscussionSummary:
        """Generate a comprehensive report for a session.

        Args:
            session_id: The session ID
            custom_instructions: Optional user instructions for report customization
            model: The model to use for generation (if None, uses config's orchestrator_model)

        Returns:
            DiscussionSummary with the generated report
        """
        # Load session data
        session_data = db.load_session_full(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")

        # Parse data
        topic = session_data.get('topic', 'Unknown Topic')
        turns_data = session_data.get('turns', [])
        segments_data = session_data.get('segments', [])
        config_data = session_data.get('config', {})
        if isinstance(config_data, str):
            config_data = json.loads(config_data)

        # Get model using same logic as orchestrator
        model = model or self._get_model_name(config_data)

        # Convert to objects
        turns = [DiscussionTurn(**t) if isinstance(t, dict) else t for t in turns_data]
        segments = [DiscussionSegment(**s) if isinstance(s, dict) else s for s in segments_data]

        # Build discussion text with segment markers
        discussion_text = ""
        current_segment = 0
        for t in turns:
            if t.segment != current_segment:
                current_segment = t.segment
                discussion_text += f"\n\n=== SEGMENT {current_segment} ===\n\n"
            discussion_text += f"{t.agent_name} ({t.persona}): {t.content}\n\n"

        # Build segment reports base
        segment_reports = []
        for seg in segments:
            segment_turns = [t for t in turns if t.segment == seg.segment_number]
            seg_text = "\n".join([f"{t.agent_name}: {t.content}" for t in segment_turns[:10]])

            # Generate segment summary
            segment_summary = await self._generate_segment_summary(
                seg.segment_number, seg_text, seg.summary, model
            )

            agent_contributions = {}
            for turn in segment_turns:
                if turn.agent_name not in agent_contributions:
                    agent_contributions[turn.agent_name] = []
                agent_contributions[turn.agent_name].append(
                    turn.content[:150] + "..." if len(turn.content) > 150 else turn.content
                )

            segment_reports.append({
                "segment_number": seg.segment_number,
                "summary": segment_summary or seg.summary or f"Segment {seg.segment_number} discussion",
                "key_developments": [],
                "agent_contributions": {k: v[0] for k, v in agent_contributions.items() if v},
                "decisions_made": [],
                "open_questions": [],
            })

        # Build fallback content
        fallback_problem = f"Discussion on: {topic}"
        fallback_answer = f"The council discussed '{topic}' across {len(segments)} segment(s) with {len(turns)} turns. "
        if turns:
            key_contributors = list(set([t.agent_name for t in turns]))[:5]
            fallback_answer += f"Key contributors: {', '.join(key_contributors)}. "
            for t in turns[:3]:
                if len(t.content) > 50:
                    fallback_answer += f"{t.agent_name} noted: {t.content[:200]}... "
                    break

        # Build custom instructions section
        custom_section = ""
        if custom_instructions:
            custom_section = f"""
CUSTOM USER INSTRUCTIONS:
{custom_instructions}

Please incorporate these instructions into the report format and style."""

        prompt = f"""You are creating a comprehensive SOLUTIONING DOCUMENT based on a multi-agent council discussion.{custom_section}

TOPIC: {topic}

FULL DISCUSSION TRANSCRIPT:
{discussion_text}

SEGMENT SUMMARIES:
"""
        for seg_report in segment_reports:
            prompt += f"\nSegment {seg_report['segment_number']}: {seg_report['summary']}\n"

        prompt += f"""

Your task is to analyze this discussion and create a detailed solutioning document. Return ONLY a JSON response in this exact format:

{{
    "problem_statement": "Clear, concise statement of the problem/question - MUST be non-empty",
    "key_points": ["Key insight 1", "Key insight 2", ...],
    "consensus_reached": true/false,
    "disagreements": ["Description of disagreement 1", ...],

    "solution_options": [
        {{
            "option_name": "Name of option/solution",
            "description": "Detailed description",
            "pros": ["Advantage 1", ...],
            "cons": ["Disadvantage 1", ...],
            "supporters": ["AgentName1"],
            "opposers": ["AgentName2"]
        }}
    ],

    "selected_solution": "Name of selected solution or null",
    "selection_reasoning": "Why this solution was chosen",

    "agent_analyses": [
        {{
            "agent_name": "Agent Name",
            "persona": "Persona type",
            "critical_points": ["Point 1", ...],
            "key_arguments": ["Argument 1", ...],
            "tools_used": ["tool1", ...],
            "stance": "supportive|opposed|neutral|skeptical"
        }}
    ],

    "segment_analyses": [
        {{
            "segment_number": 1,
            "key_developments": ["What happened"],
            "decisions_made": ["Decisions"],
            "open_questions": ["Questions"]
        }}
    ],

    "final_answer": "Direct answer to original question - MUST be non-empty",
    "justification": "Reasoning - MUST be non-empty",
    "implementation_steps": ["Step 1", ...],
    "risks_and_mitigations": ["Risk: ... | Mitigation: ..."],
    "action_items": ["Action 1", ...],
    "final_recommendation": "Executive summary - MUST be non-empty"
}}

CRITICAL: All fields marked MUST be non-empty. Even without consensus, describe what WAS discussed.

FALLBACK (use if sparse):
- Problem: {fallback_problem}
- Summary: {fallback_answer}"""

        # Call LLM using same pattern as orchestrator
        litellm_proxy = config_data.get('litellm_proxy')
        completion_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": 4000,
        }
        if litellm_proxy:
            completion_kwargs["api_base"] = litellm_proxy.get('api_base')
            completion_kwargs["api_key"] = litellm_proxy.get('api_key')

        response = completion(**completion_kwargs)
        content = response.choices[0].message.content

        # Parse JSON
        parsed = self._extract_json(content)

        # Merge segment analyses
        for seg_analysis in parsed.get("segment_analyses", []):
            for seg_report in segment_reports:
                if seg_report["segment_number"] == seg_analysis.get("segment_number"):
                    seg_report["key_developments"] = seg_analysis.get("key_developments", [])
                    seg_report["decisions_made"] = seg_analysis.get("decisions_made", [])
                    seg_report["open_questions"] = seg_analysis.get("open_questions", [])

        # Apply fallbacks for empty fields
        problem_statement = parsed.get("problem_statement") or fallback_problem
        final_answer = parsed.get("final_answer") or fallback_answer
        justification = parsed.get("justification") or self._generate_justification(
            parsed.get("consensus_reached", False), topic, parsed.get("key_points", [])
        )
        final_recommendation = parsed.get("final_recommendation") or self._generate_recommendation(
            topic, parsed.get("selected_solution")
        )

        summary = DiscussionSummary(
            topic=topic,
            start_time=session_data.get('start_time', datetime.now().isoformat()),
            end_time=datetime.now().isoformat(),
            total_turns=len(turns),
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

        # Save to database
        self._save_report(session_id, summary)

        return summary

    async def _generate_segment_summary(
        self,
        segment_number: int,
        segment_text: str,
        existing_summary: str,
        model: str = "kimi-latest"
    ) -> str:
        """Generate a summary for a single segment."""
        if existing_summary and len(existing_summary) > 20:
            return existing_summary

        if not segment_text:
            return f"Segment {segment_number} - No discussion content"

        prompt = f"""Summarize this discussion segment in 2-3 sentences:

{segment_text[:2000]}

Provide a concise summary of what was discussed:"""

        try:
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 200,
            }
            if self.litellm_proxy:
                completion_kwargs["api_base"] = self.litellm_proxy.api_base
                completion_kwargs["api_key"] = self.litellm_proxy.api_key

            response = completion(**completion_kwargs)
            return response.choices[0].message.content.strip()
        except Exception:
            return f"Segment {segment_number} discussion"

    def _extract_json(self, content: str) -> dict:
        """Extract JSON from LLM response."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        return {}

    def _generate_justification(self, consensus: bool, topic: str, key_points: list) -> str:
        """Generate fallback justification."""
        consensus_status = "reached consensus" if consensus else "explored multiple perspectives"
        points_text = "; ".join(key_points[:3]) if key_points else "Various viewpoints were considered"
        return f"The council {consensus_status} on '{topic}'. Key considerations: {points_text}"

    def _generate_recommendation(self, topic: str, selected_solution: Optional[str]) -> str:
        """Generate fallback recommendation."""
        if selected_solution:
            return f"Based on the discussion of '{topic}', the council recommends proceeding with: {selected_solution}"
        return f"Based on the discussion of '{topic}', the council suggests further exploration of the topic."

    def _save_report(self, session_id: str, summary: DiscussionSummary):
        """Save the generated report to the database."""
        try:
            db.save_session_summary(session_id, summary.model_dump())
        except Exception as e:
            print(f"[REPORT SERVICE] Warning: Could not save report: {e}")

    def get_existing_report(self, session_id: str) -> Optional[dict]:
        """Get an existing report if available."""
        session_data = db.load_session_full(session_id)
        if not session_data:
            return None

        summary_data = {}
        if session_data.get('summary'):
            try:
                summary_data = json.loads(session_data['summary'])
            except json.JSONDecodeError:
                pass

        if not summary_data:
            return None

        return {
            "session_id": session_id,
            "topic": summary_data.get('topic', session_data.get('topic', 'Unknown Topic')),
            "status": session_data.get('status', 'unknown'),
            "start_time": summary_data.get('start_time', session_data.get('start_time')),
            "end_time": summary_data.get('end_time', session_data.get('end_time')),
            "total_turns": summary_data.get('total_turns', session_data.get('current_turn', 0)),
            "problem_statement": summary_data.get('problem_statement', ''),
            "final_answer": summary_data.get('final_answer', ''),
            "justification": summary_data.get('justification', ''),
            "final_recommendation": summary_data.get('final_recommendation', ''),
            "solution_options": summary_data.get('solution_options', []),
            "selected_solution": summary_data.get('selected_solution'),
            "selection_reasoning": summary_data.get('selection_reasoning', ''),
            "implementation_steps": summary_data.get('implementation_steps', []),
            "risks_and_mitigations": summary_data.get('risks_and_mitigations', []),
            "action_items": summary_data.get('action_items', []),
            "consensus_reached": summary_data.get('consensus_reached', False),
            "key_points": summary_data.get('key_points', []),
            "disagreements": summary_data.get('disagreements', []),
            "segment_reports": summary_data.get('segment_reports', []),
            "agent_analyses": summary_data.get('agent_analyses', []),
            "turns": session_data.get('turns', []),
            "segments": session_data.get('segments', []),
        }
