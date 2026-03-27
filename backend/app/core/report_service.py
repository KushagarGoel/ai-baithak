"""Service for generating comprehensive discussion reports."""

import json
from datetime import datetime
from typing import Optional
from litellm import completion

from app.core.database import db
from app.models.schemas import (
    DiscussionSummary, DiscussionTurn, DiscussionSegment,
    SegmentReport, SolutionOption, AgentAnalysis
)


class ReportService:
    """Service for generating and managing discussion reports."""

    def __init__(self, litellm_proxy=None):
        self.litellm_proxy = litellm_proxy

    def _get_model_name(self, config_data: dict) -> str:
        """Get properly formatted model name using same logic as agent."""
        orchestrator_model = config_data.get('orchestrator_model', 'openai/gpt-4o-mini')
        if self.litellm_proxy and not orchestrator_model.startswith("openai/"):
            return f"openai/{orchestrator_model}"
        return orchestrator_model

    async def generate_report(
        self,
        session_id: str,
        custom_instructions: Optional[str] = None,
        model: Optional[str] = None
    ) -> DiscussionSummary:
        """Generate a comprehensive report for a session."""
        # Load session data
        session_data = db.load_session_full(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")

        topic = session_data.get('topic', 'Unknown Topic')
        turns_data = session_data.get('turns', [])
        segments_data = session_data.get('segments', [])
        config_data = session_data.get('config', {})
        if isinstance(config_data, str):
            config_data = json.loads(config_data)

        model = model or self._get_model_name(config_data)

        turns = [DiscussionTurn(**t) if isinstance(t, dict) else t for t in turns_data]
        segments = [DiscussionSegment(**s) if isinstance(s, dict) else s for s in segments_data]

        # Build structured segment reports
        segment_reports = await self._build_segment_reports(turns, segments, model)

        # Build agent participation map
        agent_participation = self._build_agent_participation(turns)

        # Build analysis prompt
        custom_section = ""
        if custom_instructions:
            custom_section = f"\n\nCUSTOM USER INSTRUCTIONS:\n{custom_instructions}\n\nIncorporate these into your analysis."

        prompt = self._build_analysis_prompt(
            topic=topic,
            turns=turns,
            segments=segments,
            segment_reports=segment_reports,
            agent_participation=agent_participation,
            custom_section=custom_section
        )

        # Call LLM
        litellm_proxy = config_data.get('litellm_proxy')
        completion_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 6000,
        }
        if litellm_proxy:
            completion_kwargs["api_base"] = litellm_proxy.get('api_base')
            completion_kwargs["api_key"] = litellm_proxy.get('api_key')

        response = completion(**completion_kwargs)
        content = response.choices[0].message.content

        parsed = self._extract_json(content)

        summary = self._build_summary_from_parsed(
            parsed=parsed,
            topic=topic,
            turns=turns,
            segments=segments,
            segment_reports=segment_reports,
            session_data=session_data
        )

        self._save_report(session_id, summary)
        return summary

    async def _build_segment_reports(
        self,
        turns: list[DiscussionTurn],
        segments: list[DiscussionSegment],
        model: str
    ) -> list[dict]:
        """Build proper segment reports with AI-generated summaries."""
        segment_reports = []

        for seg in segments:
            segment_turns = [t for t in turns if t.segment == seg.segment_number]
            if not segment_turns:
                continue

            conversation_excerpt = []
            for t in segment_turns:
                conversation_excerpt.append(f"{t.agent_name} ({t.persona}): {t.content[:500]}")

            segment_summary = await self._generate_segment_summary(
                seg.segment_number,
                "\n\n".join(conversation_excerpt[:15]),
                seg.summary,
                model
            )

            agent_contributions = {}
            for turn in segment_turns:
                if turn.agent_name not in agent_contributions:
                    # Store first contribution as string
                    agent_contributions[turn.agent_name] = turn.content

            segment_reports.append({
                "segment_number": seg.segment_number,
                "summary": segment_summary,
                "key_developments": [],
                "agent_contributions": agent_contributions,
                "decisions_made": [],
                "open_questions": [],
            })

        return segment_reports

    def _build_agent_participation(self, turns: list[DiscussionTurn]) -> dict:
        """Build map of agent participation."""
        participation = {}
        for turn in turns:
            if turn.agent_name not in participation:
                participation[turn.agent_name] = {
                    "persona": turn.persona,
                    "message_count": 0,
                    "total_chars": 0,
                    "key_messages": []
                }
            participation[turn.agent_name]["message_count"] += 1
            participation[turn.agent_name]["total_chars"] += len(turn.content)
            if len(participation[turn.agent_name]["key_messages"]) < 3:
                participation[turn.agent_name]["key_messages"].append(turn.content[:300])
        return participation

    def _build_analysis_prompt(
        self,
        topic: str,
        turns: list[DiscussionTurn],
        segments: list[DiscussionSegment],
        segment_reports: list[dict],
        agent_participation: dict,
        custom_section: str
    ) -> str:
        """Build the analysis prompt for the LLM."""

        segments_text = ""
        for seg in segment_reports:
            segments_text += f"\n=== SEGMENT {seg['segment_number']} ===\n"
            segments_text += f"Summary: {seg['summary']}\n"
            segments_text += f"Agents involved: {', '.join(seg['agent_contributions'].keys())}\n"

        agents_text = "\n".join([
            f"- {name} ({data['persona']}): {data['message_count']} messages"
            for name, data in agent_participation.items()
        ])

        prompt = f"""You are analyzing a multi-agent council discussion to create a structured solutioning report.{custom_section}

TOPIC DISCUSSED: {topic}

PARTICIPATING AGENTS:
{agents_text}

DISCUSSION SEGMENTS:
{segments_text}

---

Your task is to produce a COMPREHENSIVE STRUCTURED ANALYSIS. Return ONLY a JSON object in this exact format:

{{
    "problem_statement": "A clear, detailed statement of what problem/question the council was addressing",

    "key_points": [
        "Key insight or finding 1",
        "Key insight or finding 2"
    ],

    "consensus_reached": true,

    "disagreements": [
        "Description of area where agents disagreed"
    ],

    "solution_options": [
        {{
            "option_name": "Name of the approach/solution",
            "description": "2-3 sentence description of this approach",
            "pros": ["Advantage 1", "Advantage 2"],
            "cons": ["Disadvantage 1", "Disadvantage 2"],
            "supporters": ["AgentName1", "AgentName2"],
            "opposers": ["AgentName3"]
        }}
    ],

    "selected_solution": "Name of the best solution OR null if no consensus",
    "selection_reasoning": "Why this solution was selected, or why no consensus was reached",

    "agent_analyses": [
        {{
            "agent_name": "Agent Name",
            "persona": "Their persona/role",
            "stance": "supportive|opposed|neutral|skeptical",
            "critical_points": ["Main point they argued", "Another key point"],
            "key_arguments": ["Their primary argument", "Supporting argument"],
            "tools_used": ["tool1", "tool2"]
        }}
    ],

    "segment_analyses": [
        {{
            "segment_number": 1,
            "key_developments": ["What was discovered/decided", "Progress made"],
            "decisions_made": ["Decision 1"],
            "open_questions": ["Question remaining"]
        }}
    ],

    "final_answer": "A structured summary with:\n- Overall Approach: [brief summary]\n- Key Findings: [bullet points]\n- Recommended Path Forward: [clear recommendation]",

    "justification": "Detailed reasoning for the final answer, explaining the council's thinking process",

    "implementation_steps": ["Step 1: ...", "Step 2: ..."],

    "risks_and_mitigations": ["Risk: ... | Mitigation: ..."],

    "action_items": ["Action item 1", "Action item 2"],

    "final_recommendation": "Executive summary (2-3 sentences) of the council's conclusion"
}}

---

CRITICAL REQUIREMENTS:

1. **solution_options MUST contain at least 2-3 distinct approaches** discussed by agents. Each must have:
   - Clear option_name and description
   - At least 2 pros and 2 cons
   - Supporters and opposers from the agent list

2. **agent_analyses MUST contain one entry per agent** who participated. Each must have:
   - Their stance on the overall topic
   - 2-3 critical points they raised
   - Their key arguments

3. **final_answer MUST be structured with bullet points** covering:
   - Overall Approach
   - Key Findings
   - Recommended Path Forward

4. **segment_analyses MUST analyze each segment** for:
   - Key developments (what progress was made)
   - Decisions made
   - Open questions

5. All string fields must be non-empty and meaningful.

Analyze the segments carefully and extract these insights from the discussion."""

        return prompt

    def _build_summary_from_parsed(
        self,
        parsed: dict,
        topic: str,
        turns: list[DiscussionTurn],
        segments: list[DiscussionSegment],
        segment_reports: list[dict],
        session_data: dict
    ) -> DiscussionSummary:
        """Build DiscussionSummary from parsed JSON with smart fallbacks."""

        # Merge segment analyses
        for seg_analysis in parsed.get("segment_analyses", []):
            for seg_report in segment_reports:
                if seg_report["segment_number"] == seg_analysis.get("segment_number"):
                    seg_report["key_developments"] = seg_analysis.get("key_developments", [])
                    seg_report["decisions_made"] = seg_analysis.get("decisions_made", [])
                    seg_report["open_questions"] = seg_analysis.get("open_questions", [])

        # Ensure solution_options exists
        solution_options = parsed.get("solution_options", [])
        if not solution_options:
            solution_options = self._infer_solution_options(turns, parsed.get("agent_analyses", []))

        # Ensure agent_analyses exists
        agent_analyses = parsed.get("agent_analyses", [])
        if not agent_analyses:
            agent_analyses = self._infer_agent_analyses(turns)

        # Build proper final_answer
        final_answer = parsed.get("final_answer", "")
        if not final_answer or len(final_answer) < 200:
            final_answer = self._build_structured_final_answer(
                topic=topic,
                key_points=parsed.get("key_points", []),
                solution_options=solution_options,
                selected_solution=parsed.get("selected_solution"),
                agent_analyses=agent_analyses
            )

        problem_statement = parsed.get("problem_statement") or f"The council discussed: {topic}"

        justification = parsed.get("justification") or self._generate_justification(
            parsed.get("consensus_reached", False),
            topic,
            parsed.get("key_points", [])
        )

        final_recommendation = parsed.get("final_recommendation") or self._generate_recommendation(
            topic,
            parsed.get("selected_solution")
        )

        # Convert to proper schema objects
        segment_report_objects = [
            SegmentReport(
                segment_number=seg["segment_number"],
                summary=seg["summary"],
                key_developments=seg.get("key_developments", []),
                agent_contributions=seg.get("agent_contributions", {}),
                decisions_made=seg.get("decisions_made", []),
                open_questions=seg.get("open_questions", [])
            ) for seg in segment_reports
        ]

        solution_option_objects = [
            SolutionOption(**opt) for opt in solution_options
        ] if solution_options else []

        agent_analysis_objects = [
            AgentAnalysis(**analysis) for analysis in agent_analyses
        ] if agent_analyses else []

        return DiscussionSummary(
            topic=topic,
            start_time=session_data.get('start_time', datetime.now().isoformat()),
            end_time=datetime.now().isoformat(),
            total_turns=len(turns),
            key_points=parsed.get("key_points", []),
            consensus_reached=parsed.get("consensus_reached", False),
            disagreements=parsed.get("disagreements", []),
            action_items=parsed.get("action_items", []),
            problem_statement=problem_statement,
            solution_options=solution_option_objects,
            selected_solution=parsed.get("selected_solution"),
            selection_reasoning=parsed.get("selection_reasoning", ""),
            segment_reports=segment_report_objects,
            agent_analyses=agent_analysis_objects,
            final_recommendation=final_recommendation,
            final_answer=final_answer,
            justification=justification,
            implementation_steps=parsed.get("implementation_steps", []),
            risks_and_mitigations=parsed.get("risks_and_mitigations", []),
        )

    def _infer_solution_options(
        self,
        turns: list[DiscussionTurn],
        agent_analyses: list[dict]
    ) -> list[dict]:
        """Infer solution options from discussion if LLM didn't provide them."""
        agent_positions = {}
        for turn in turns:
            if turn.agent_name not in agent_positions:
                agent_positions[turn.agent_name] = []
            agent_positions[turn.agent_name].append(turn.content)

        options = []
        stances = ["approach", "solution", "method"]

        for i, (agent_name, messages) in enumerate(list(agent_positions.items())[:3]):
            options.append({
                "option_name": f"{agent_name}'s {stances[i % len(stances)]}",
                "description": f"Approach advocated by {agent_name} based on their contributions",
                "pros": ["Detailed consideration", "Agent expertise"],
                "cons": ["May have limitations", "Alternative viewpoints exist"],
                "supporters": [agent_name],
                "opposers": [a for a in agent_positions.keys() if a != agent_name][:2]
            })

        return options

    def _infer_agent_analyses(self, turns: list[DiscussionTurn]) -> list[dict]:
        """Infer agent analyses from discussion if LLM didn't provide them."""
        agent_data = {}

        for turn in turns:
            if turn.agent_name not in agent_data:
                agent_data[turn.agent_name] = {
                    "persona": turn.persona,
                    "messages": [],
                    "tools_used": set()
                }
            agent_data[turn.agent_name]["messages"].append(turn.content)
            for tool_call in turn.tool_calls:
                agent_data[turn.agent_name]["tools_used"].add(tool_call.name)

        analyses = []
        for agent_name, data in agent_data.items():
            key_messages = [data["messages"][0]] if data["messages"] else ["Participated in discussion"]
            if len(data["messages"]) > 1:
                key_messages.append(data["messages"][-1])

            analyses.append({
                "agent_name": agent_name,
                "persona": data["persona"],
                "stance": "neutral",
                "critical_points": [m[:150] + "..." if len(m) > 150 else m for m in key_messages[:2]],
                "key_arguments": ["Contributed to the discussion"],
                "tools_used": list(data["tools_used"])
            })

        return analyses

    def _build_structured_final_answer(
        self,
        topic: str,
        key_points: list[str],
        solution_options: list[dict],
        selected_solution: Optional[str],
        agent_analyses: list[dict]
    ) -> str:
        """Build a structured final answer with bullet points."""

        answer = f"""## Overall Approach

The council engaged in a structured discussion on "{topic}" to explore multiple perspectives and arrive at a well-reasoned conclusion.

## Key Findings

"""
        for point in key_points[:5]:
            answer += f"- {point}\n"

        if not key_points:
            answer += "- Multiple perspectives were considered\n"
            answer += "- Various approaches were evaluated\n"

        answer += "\n## Agent Perspectives\n\n"
        for analysis in agent_analyses[:4]:
            answer += f"**{analysis['agent_name']}** ({analysis.get('persona', 'Unknown')}):\n"
            answer += f"- Stance: {analysis.get('stance', 'neutral')}\n"
            if analysis.get('critical_points'):
                answer += f"- Key Point: {analysis['critical_points'][0][:100]}...\n"
            answer += "\n"

        answer += "## Solution Options Considered\n\n"
        for opt in solution_options[:3]:
            answer += f"**{opt.get('option_name', 'Unnamed')}**\n"
            answer += f"- Pros: {', '.join(opt.get('pros', ['None'])[:2])}\n"
            answer += f"- Cons: {', '.join(opt.get('cons', ['None'])[:2])}\n"
            answer += f"- Supported by: {', '.join(opt.get('supporters', ['Unknown']))}\n\n"

        answer += "\n## Recommended Path Forward\n\n"
        if selected_solution:
            answer += f"The council recommends proceeding with: **{selected_solution}**\n\n"
        else:
            answer += "The council suggests further exploration of the discussed options.\n\n"

        return answer

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

        prompt = f"""Summarize this discussion segment in 2-3 sentences, focusing on what was discussed and any decisions or insights:

{segment_text[:2000]}

Provide a concise summary:"""

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
