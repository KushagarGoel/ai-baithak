"""Simplified Agent Council Dashboard - Map personas to your LiteLLM models."""

import asyncio
import os
import pickle
import time
from datetime import datetime

import streamlit as st

from agent_council import CouncilOrchestrator
from agent_council.config import AgentConfig, CouncilConfig, LiteLLMProxyConfig
from agent_council.personas import PERSONAS

# Page config
st.set_page_config(
    page_title="Agent Council - Simple",
    page_icon="🏛️",
    layout="wide",
)

# Custom CSS - Dark mode compatible
st.markdown(
    """
<style>
.agent-card {
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
    border-left: 4px solid #6366f1;
    background-color: rgba(99, 102, 241, 0.1);
    color: inherit;
}
.message-lazy { border-left-color: #22c55e; background-color: rgba(34, 197, 94, 0.15); }
.message-smart { border-left-color: #f59e0b; background-color: rgba(245, 158, 11, 0.15); }
.message-skeptic { border-left-color: #ef4444; background-color: rgba(239, 68, 68, 0.15); }
.message-creative { border-left-color: #a855f7; background-color: rgba(168, 85, 247, 0.15); }
.message-pragmatic { border-left-color: #3b82f6; background-color: rgba(59, 130, 246, 0.15); }
.message-empath { border-left-color: #ec4899; background-color: rgba(236, 72, 153, 0.15); }
.message-orchestrator { border-left-color: #eab308; background-color: rgba(234, 179, 8, 0.15); }
.agent-header {
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: inherit;
}
.persona-tag {
    font-size: 0.75rem;
    padding: 0.1rem 0.5rem;
    border-radius: 1rem;
    background-color: rgba(128, 128, 128, 0.3);
    margin-left: 0.5rem;
}
.message-content {
    color: inherit;
    line-height: 1.6;
}
</style>
""",
    unsafe_allow_html=True,
)


def get_persona_class(persona_key: str) -> str:
    """Get CSS class for a persona."""
    mapping = {
        "the_lazy_one": "message-lazy",
        "the_egomaniac": "message-smart",
        "the_devils_advocate": "message-skeptic",
        "the_creative": "message-creative",
        "the_pragmatist": "message-pragmatic",
        "the_empath": "message-empath",
        "the_researcher": "message-pragmatic",
    }
    return mapping.get(persona_key, "agent-card")


def render_message(turn, container=None):
    """Render a single message."""
    persona_key = None
    for pk, p in PERSONAS.items():
        if p.name == turn.persona:
            persona_key = pk
            break

    css_class = get_persona_class(persona_key) if persona_key else "agent-card"

    html = f"""
    <div class="agent-card {css_class}">
        <div class="agent-header">
            {turn.agent_name}
            <span class="persona-tag">{turn.persona}</span>
        </div>
        <div class="message-content">{turn.content.replace(chr(10), "<br>")}</div>
    </div>
    """

    if container:
        container.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(html, unsafe_allow_html=True)


# Initialize session state
if "running" not in st.session_state:
    st.session_state.running = False
if "turns" not in st.session_state:
    st.session_state.turns = []
if "summary" not in st.session_state:
    st.session_state.summary = None
if "config" not in st.session_state:
    st.session_state.config = None
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "turn_in_progress" not in st.session_state:
    st.session_state.turn_in_progress = False
if "pending_user_message" not in st.session_state:
    st.session_state.pending_user_message = None
if "trigger_next_turn" not in st.session_state:
    st.session_state.trigger_next_turn = False


def save_session_state():
    """Save current session to disk."""
    sessions_dir = os.path.join(os.getcwd(), "sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    # Generate session ID if not exists
    if not st.session_state.session_id:
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    session_file = os.path.join(
        sessions_dir, f"session_{st.session_state.session_id}.pkl"
    )

    # Get data from orchestrator
    tokens_used = 0
    segments_data = []
    current_segment = 0
    if "orchestrator" in st.session_state:
        if hasattr(st.session_state.orchestrator, 'total_tokens_used'):
            tokens_used = st.session_state.orchestrator.total_tokens_used
        if hasattr(st.session_state.orchestrator, 'segments'):
            # Convert segments to plain dicts for pickle safety
            for seg in st.session_state.orchestrator.segments:
                segments_data.append({
                    'segment_number': getattr(seg, 'segment_number', 0),
                    'start_turn': getattr(seg, 'start_turn', 1),
                    'end_turn': getattr(seg, 'end_turn', None),
                    'summary': getattr(seg, 'summary', ''),
                    'orchestrator_message': getattr(seg, 'orchestrator_message', ''),
                })
        if hasattr(st.session_state.orchestrator, 'current_segment'):
            current_segment = st.session_state.orchestrator.current_segment

    # Convert turns to plain dicts for pickle safety
    turns_data = []
    for turn in st.session_state.turns:
        turns_data.append({
            'turn_number': getattr(turn, 'turn_number', 0),
            'agent_name': getattr(turn, 'agent_name', ''),
            'persona': getattr(turn, 'persona', ''),
            'content': getattr(turn, 'content', ''),
            'timestamp': getattr(turn, 'timestamp', 0),
            'tool_calls': getattr(turn, 'tool_calls', []),
            'tool_results': getattr(turn, 'tool_results', []),
            'segment': getattr(turn, 'segment', 0),
        })

    # Convert config to dict for pickle safety
    config_dict = None
    if st.session_state.config:
        config = st.session_state.config
        config_dict = {
            'topic': config.topic,
            'max_duration_minutes': config.max_duration_minutes,
            'max_turns': config.max_turns,
            'min_turns': config.min_turns,
            'agents': [
                {
                    'name': a.name,
                    'model': a.model,
                    'persona': a.persona,
                    'temperature': a.temperature,
                    'max_tokens': a.max_tokens,
                    'tools_enabled': a.tools_enabled,
                }
                for a in config.agents
            ],
            'orchestrator_model': config.orchestrator_model,
            'orchestrator_frequency': config.orchestrator_frequency,
            'context_compression_threshold': config.context_compression_threshold,
            'session_id': config.session_id,
        }
        if config.litellm_proxy:
            config_dict['litellm_proxy'] = {
                'api_base': config.litellm_proxy.api_base,
                'api_key': config.litellm_proxy.api_key,
            }

    # Save session data
    session_data = {
        "session_id": st.session_state.session_id,
        "turns": turns_data,
        "config": config_dict,
        "summary": st.session_state.summary,
        "running": st.session_state.running,
        "total_tokens": tokens_used,
        "segments": segments_data,
        "current_segment": current_segment,
    }

    try:
        with open(session_file, "wb") as f:
            pickle.dump(session_data, f)
    except TypeError as e:
        print(f"[SAVE ERROR] Cannot pickle session data: {e}")
        # Try to identify which field is causing the issue
        for key, value in session_data.items():
            try:
                pickle.dumps(value)
            except TypeError as te:
                print(f"[SAVE ERROR] Field '{key}' is not pickleable: {te}")
        # Don't crash, just skip saving
        return None

    return session_file


def load_session_state(session_file: str):
    """Load session from disk."""
    with open(session_file, "rb") as f:
        session_data = pickle.load(f)

    st.session_state.session_id = session_data["session_id"]
    st.session_state.summary = session_data["summary"]
    st.session_state.running = session_data.get("running", False)
    st.session_state.total_tokens = session_data.get("total_tokens", 0)
    st.session_state.segments = session_data.get("segments", [])
    st.session_state.current_segment = session_data.get("current_segment", 0)

    # Reconstruct config from dict
    config_dict = session_data.get("config")
    if config_dict:
        from agent_council.config import CouncilConfig, AgentConfig, LiteLLMProxyConfig
        agents = [
            AgentConfig(
                name=a['name'],
                model=a['model'],
                persona=a['persona'],
                temperature=a.get('temperature'),
                max_tokens=a.get('max_tokens'),
                tools_enabled=a.get('tools_enabled', True),
            )
            for a in config_dict.get('agents', [])
        ]
        litellm_proxy = None
        if config_dict.get('litellm_proxy'):
            litellm_proxy = LiteLLMProxyConfig(
                api_base=config_dict['litellm_proxy']['api_base'],
                api_key=config_dict['litellm_proxy']['api_key'],
            )
        st.session_state.config = CouncilConfig(
            topic=config_dict['topic'],
            max_duration_minutes=config_dict.get('max_duration_minutes', 10),
            max_turns=config_dict.get('max_turns', 20),
            min_turns=config_dict.get('min_turns', 5),
            agents=agents,
            litellm_proxy=litellm_proxy,
            orchestrator_model=config_dict.get('orchestrator_model', 'anthropic/claude-3-haiku-20240307'),
            orchestrator_frequency=config_dict.get('orchestrator_frequency', 3),
            context_compression_threshold=config_dict.get('context_compression_threshold', 40),
            session_id=config_dict.get('session_id'),
        )
    else:
        st.session_state.config = None

    # Reconstruct turn objects from dicts
    from agent_council.orchestrator import DiscussionTurn
    turns_data = session_data.get("turns", [])
    st.session_state.turns = []
    for turn_dict in turns_data:
        st.session_state.turns.append(DiscussionTurn(
            turn_number=turn_dict.get('turn_number', 0),
            agent_name=turn_dict.get('agent_name', ''),
            persona=turn_dict.get('persona', ''),
            content=turn_dict.get('content', ''),
            timestamp=turn_dict.get('timestamp', 0),
            tool_calls=turn_dict.get('tool_calls', []),
            tool_results=turn_dict.get('tool_results', []),
            segment=turn_dict.get('segment', 0),
        ))

    return session_data


def get_saved_sessions():
    """Get list of saved sessions."""
    sessions_dir = os.path.join(os.getcwd(), "sessions")
    if not os.path.exists(sessions_dir):
        return []

    sessions = []
    for filename in sorted(os.listdir(sessions_dir), reverse=True):
        if filename.startswith("session_") and filename.endswith(".pkl"):
            filepath = os.path.join(sessions_dir, filename)
            try:
                with open(filepath, "rb") as f:
                    session_data = pickle.load(f)
                # Handle both old (object) and new (dict) config formats
                config = session_data.get("config")
                if config:
                    if isinstance(config, dict):
                        topic = config.get('topic', 'Unknown')
                    else:
                        topic = getattr(config, 'topic', 'Unknown')
                else:
                    topic = 'Unknown'
                sessions.append(
                    {
                        "file": filepath,
                        "id": session_data.get("session_id", filename),
                        "topic": topic,
                        "turns": len(session_data.get("turns", [])),
                        "date": datetime.strptime(
                            session_data.get("session_id", "19700101_000000"),
                            "%Y%m%d_%H%M%S",
                        )
                        if session_data.get("session_id")
                        else datetime.now(),
                    }
                )
            except:
                pass
    return sessions


# Header
st.title("🏛️ Agent Council")
st.markdown("Configure your council and let them deliberate")


# Sidebar - Configuration
with st.sidebar:
    st.header("Session Management")

    # Load saved sessions
    saved_sessions = get_saved_sessions()
    if saved_sessions:
        st.subheader("💾 Continue Previous Session")
        session_options = {
            f"{s['topic'][:40]}... ({s['turns']} turns) - {s['date'].strftime('%Y-%m-%d %H:%M')}": s
            for s in saved_sessions
        }
        selected_session_label = st.selectbox(
            "Select session to continue",
            options=["New Session"] + list(session_options.keys()),
            index=0,
        )

        if selected_session_label != "New Session" and st.button("🔄 Load Session"):
            selected_session = session_options[selected_session_label]
            load_session_state(selected_session["file"])
            # Re-initialize orchestrator with loaded state
            if st.session_state.config:
                st.session_state.orchestrator = CouncilOrchestrator(
                    st.session_state.config
                )
                st.session_state.orchestrator.turns = st.session_state.turns
                st.session_state.orchestrator.current_turn = len(st.session_state.turns)
                st.session_state.orchestrator.start_time = time.time()
                # Restore segment data
                if hasattr(st.session_state, 'segments'):
                    st.session_state.orchestrator.segments = st.session_state.segments
                if hasattr(st.session_state, 'current_segment'):
                    st.session_state.orchestrator.current_segment = st.session_state.current_segment
                # Restore agent message histories
                for turn in st.session_state.turns:
                    st.session_state.orchestrator._broadcast_turn(turn)
            st.rerun()

    st.divider()
    st.header("Configuration")

    # LiteLLM Proxy
    st.subheader("LiteLLM Proxy")
    proxy_url = st.text_input(
        "Proxy URL",
        value=os.getenv("LITELLM_PROXY_URL", "http://localhost:4000"),
    )
    proxy_key = st.text_input(
        "API Key",
        type="password",
        value=os.getenv("LITELLM_PROXY_KEY", ""),
    )

    st.divider()

    # Discussion Settings
    st.subheader("Discussion")
    topic = st.text_area(
        "Topic",
        placeholder="What should the council discuss?",
        height=100,
    )
    max_time = st.slider("Max Duration (minutes)", 1, 600, 5)

    # Segment/Context Settings
    st.subheader("Segment Settings")
    st.markdown("When agents exceed this message count, a new segment starts with a summary:")
    segment_threshold = st.slider(
        "Messages before new segment",
        min_value=5,
        max_value=100,
        value=20,
        step=5,
        help="When any agent reaches this message count, the discussion will start a new segment with a summary of prior discussion"
    )

    st.divider()

    # Agent Assignment
    st.subheader("Assign Personas to Models")
    st.markdown("Enter your LiteLLM model names and select personas:")

    # Default agent configuration (6 agents as shown in screenshot)
    default_agents = [
        ("kimi-latest", "the_lazy_one"),           # Model 1: The Lazy One
        ("open-fast", "the_egomaniac"),            # Model 2: The Know-It-All
        ("glm-latest", "the_devils_advocate"),     # Model 3: Devil's Advocate
        ("open-large", "the_creative"),            # Model 4: The Creative
        ("glm-latest", "the_researcher"),          # Model 5: The Researcher
        ("kimi-latest", "the_pragmatist"),         # Model 6: The Pragmatist
    ]

    # Dynamic agent rows
    if "agent_rows" not in st.session_state:
        st.session_state.agent_rows = 6  # Default to 6 agents

    agent_configs = []
    persona_options = list(PERSONAS.keys())
    persona_labels = {
        k: f"{v.name}" for k, v in PERSONAS.items() if k != "the_orchestrator"
    }

    # Available models dropdown options
    available_models = [
        "kimi-latest",
        "open-fast",
        "open-large",
        "glm-latest",
        "minimaxai/minimax-m2",
    ]

    for i in range(st.session_state.agent_rows):
        # Get default for this row, or use first default if beyond defaults
        default = default_agents[i] if i < len(default_agents) else default_agents[0]

        cols = st.columns([2, 2])
        with cols[0]:
            model = st.selectbox(
                f"Model {i + 1}",
                options=available_models,
                index=available_models.index(default[0]) if default[0] in available_models else 0,
                key=f"model_{i}",
            )
        with cols[1]:
            persona = st.selectbox(
                f"Persona {i + 1}",
                options=list(persona_labels.keys()),
                format_func=lambda x: persona_labels[x],
                index=list(persona_labels.keys()).index(default[1]) if default[1] in persona_labels else 0,
                key=f"persona_{i}",
            )
        if model.strip():
            agent_configs.append((model.strip(), persona))

    # Add/remove buttons
    cols = st.columns(2)
    with cols[0]:
        if st.button("+ Add Agent") and st.session_state.agent_rows < 10:
            st.session_state.agent_rows += 1
            st.rerun()
    with cols[1]:
        if st.button("- Remove") and st.session_state.agent_rows > 2:
            st.session_state.agent_rows -= 1
            st.rerun()

    st.divider()

    # Orchestrator model
    st.subheader("Orchestrator (Manager)")
    orchestrator_model = st.selectbox(
        "Orchestrator Model",
        options=available_models,
        index=0,  # Default to kimi-latest (first in list)
        help="Model to use for the manager that guides discussion",
    )


# Main area
# Check if we have a loaded session
has_loaded_session = (
    st.session_state.config is not None
    and len(st.session_state.turns) > 0
    and not st.session_state.summary
)

# Get topic from loaded session if available
if has_loaded_session and st.session_state.config:
    topic = st.session_state.config.topic
    agent_configs = [
        (agent.model, agent.persona) for agent in st.session_state.config.agents
    ]

if not has_loaded_session:
    if not topic.strip():
        st.info("👈 Enter a topic in the sidebar to begin")
        st.stop()

    if len(agent_configs) < 2:
        st.info("👈 Configure at least 2 agents with models and personas")
        st.stop()

# Show configuration summary
with st.expander("📋 Configuration Summary", expanded=True):
    cols = st.columns(4)
    with cols[0]:
        st.metric("Agents", len(agent_configs))
    with cols[1]:
        st.metric("Max Duration", f"{max_time} min")
    with cols[2]:
        st.metric("Models", len(set(m for m, _ in agent_configs)))
    with cols[3]:
        # Show token usage if orchestrator exists
        tokens_display = "0"
        if "orchestrator" in st.session_state and hasattr(st.session_state.orchestrator, 'total_tokens_used'):
            tokens = st.session_state.orchestrator.total_tokens_used
            # Format with k suffix for large numbers
            if tokens >= 1000:
                tokens_display = f"{tokens / 1000:.1f}k"
            else:
                tokens_display = str(tokens)
        st.metric("Tokens Used", tokens_display)

    st.markdown("**Agents:**")
    for model, persona in agent_configs:
        st.markdown(f"- `{model}` → **{PERSONAS[persona].name}**")


# Start button
if not st.session_state.running and not st.session_state.summary:
    if st.button(
        "🚀 Start Council Discussion", type="primary", use_container_width=True
    ):
        # Build config
        agents = [
            AgentConfig(
                name=f"{PERSONAS[persona].name} ({model})",
                model=model,
                persona=persona,
            )
            for model, persona in agent_configs
        ]

        config = CouncilConfig(
            topic=topic,
            max_duration_minutes=max_time,
            max_turns=max_time * 3,  # Approx 3 turns per minute
            agents=agents,
            litellm_proxy=LiteLLMProxyConfig(api_base=proxy_url, api_key=proxy_key),
            orchestrator_model=orchestrator_model,
            session_id=st.session_state.session_id,
            context_compression_threshold=segment_threshold,
        )

        st.session_state.config = config
        st.session_state.running = True
        st.session_state.turns = []
        st.rerun()


# Display discussion area
st.header("💬 Discussion")


def render_orchestrator_card(content: str, title: str = "Orchestrator"):
    """Render an orchestrator message card."""
    html = f"""
    <div class="agent-card message-orchestrator" style="border: 2px solid #eab308; margin-bottom: 1rem;">
        <div class="agent-header">
            {title}
            <span class="persona-tag">Manager</span>
        </div>
        <div class="message-content">{content.replace(chr(10), "<br>")}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# Show turns grouped by segments as sub-tabs
if st.session_state.turns:
    # Get orchestrator segments info if available
    orchestrator = st.session_state.get("orchestrator")
    segment_info = {}
    if orchestrator and hasattr(orchestrator, 'segments'):
        for seg in orchestrator.segments:
            segment_info[seg.segment_number] = {
                'summary': seg.summary,
                'orchestrator_message': seg.orchestrator_message,
                'start_turn': seg.start_turn,
                'end_turn': seg.end_turn,
            }

    # Get unique segments from turns
    segments = {}
    for turn in st.session_state.turns:
        seg = getattr(turn, 'segment', 0)
        if seg not in segments:
            segments[seg] = []
        segments[seg].append(turn)

    # Sort segments
    sorted_segments = sorted(segments.keys())

    # Always create tabs for segments (even if single segment for consistency)
    tab_labels = [f"Segment {s + 1}" for s in sorted_segments]
    tabs = st.tabs(tab_labels)

    # Load key insights if available
    key_insights = []
    insights_file = None
    if orchestrator and hasattr(orchestrator, '_get_session_folder'):
        try:
            session_folder = orchestrator._get_session_folder()
            insights_path = os.path.join(session_folder, "key_insights.md")
            if os.path.exists(insights_path):
                insights_file = insights_path
                with open(insights_path, "r") as f:
                    key_insights = f.read()
        except Exception:
            pass

    for i, seg_num in enumerate(sorted_segments):
        with tabs[i]:
            # Show segment header with orchestrator message for new segments (except first)
            info = segment_info.get(seg_num, {})

            if seg_num > 0 and info.get('orchestrator_message'):
                # This is a continuation segment - show the transition message (includes summary)
                render_orchestrator_card(
                    info['orchestrator_message'],
                    title=f"Segment {seg_num + 1} - Continued Discussion"
                )
                st.divider()
            elif seg_num == 0:
                # First segment - show topic
                if st.session_state.config:
                    topic_html = f"""
                    <div style="padding: 1rem; background-color: rgba(99, 102, 241, 0.1); border-radius: 0.5rem; margin-bottom: 1rem;">
                        <strong>Topic:</strong> {st.session_state.config.topic}
                    </div>
                    """
                    st.markdown(topic_html, unsafe_allow_html=True)

            # Show key insights relevant to this segment
            if key_insights and seg_num > 0:
                with st.expander("🔑 Key Insights from Prior Segments", expanded=True):
                    st.markdown(key_insights)

            # Render all turns in this segment
            for turn in segments[seg_num]:
                render_message(turn)
else:
    chat_container = st.container()
    with chat_container:
        st.info("Discussion will appear here...")

# User chat input - always available when discussion is running
if st.session_state.running and "orchestrator" in st.session_state:
    user_message = st.chat_input("💭 Share your thoughts or ask a question...")
    if user_message:
        # Queue the message to be inserted after current agent finishes
        st.session_state.pending_user_message = user_message
        st.success(
            "💭 Message queued! It will appear after the current agent responds."
        )

# Show queued message indicator
if st.session_state.pending_user_message:
    st.info(
        "⏳ Your message is queued and will appear after the current agent responds..."
    )

# Run discussion - use a single-turn approach for real-time updates
if st.session_state.running:
    config = st.session_state.config

    # Initialize orchestrator if not exists
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = CouncilOrchestrator(config)
        st.session_state.orchestrator.start_time = time.time()
        st.session_state.turn_in_progress = False

        # Set up initial topic for all agents
        initial_context = f"""Welcome to the Council Discussion.

TOPIC: {config.topic}

This is a deliberative discussion to thoroughly explore this topic. You are all expert advisors with different perspectives.

Guidelines:
- Engage authentically as your persona
- Listen to others and respond to their points
- Use tools when you need information
- Aim for depth over speed

Let's begin. Each of you will have a chance to share your initial thoughts."""

        for agent in st.session_state.orchestrator.agents:
            agent.add_message("user", initial_context)

    orchestrator = st.session_state.orchestrator
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Run one turn at a time for real-time display
    # Reset turn_in_progress if there's a pending message (previous turn was interrupted)
    if st.session_state.pending_user_message and st.session_state.turn_in_progress:
        st.session_state.turn_in_progress = False

    if not st.session_state.turn_in_progress and orchestrator._should_continue():
        st.session_state.turn_in_progress = True

        async def run_single_turn():
            orchestrator.current_turn += 1

            # Select speaker
            speaker = orchestrator._select_next_speaker()
            if not speaker:
                return None

            # Build context
            context = orchestrator._build_context_for_agent(speaker)

            # Get response
            status_text.text(
                f"Turn {orchestrator.current_turn} - {speaker.config.name} is thinking..."
            )
            response = await speaker.think_and_respond(context)

            # Create turn
            from agent_council.orchestrator import DiscussionTurn

            turn = DiscussionTurn(
                turn_number=orchestrator.current_turn,
                agent_name=response["agent_name"],
                persona=response["persona"],
                content=response["content"],
                tool_calls=response.get("tool_calls", []),
                tool_results=response.get("tool_results", []),
                segment=orchestrator.current_segment,
            )

            # Record and broadcast
            orchestrator.turns.append(turn)
            orchestrator._broadcast_turn(turn)

            # Orchestrator interjection
            if (
                orchestrator.current_turn % orchestrator.config.orchestrator_frequency
                == 0
            ):
                await orchestrator._orchestrator_interjection()

            # Check if we need to start a new segment (context overflow)
            await orchestrator._check_and_start_new_segment()

            return turn

        # Run one turn
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            turn = loop.run_until_complete(run_single_turn())
            if turn:
                # Sync all turns from orchestrator (includes segment transitions)
                st.session_state.turns = orchestrator.turns.copy()
        finally:
            loop.close()

        st.session_state.turn_in_progress = False

        # Update progress
        progress = min(orchestrator.current_turn / orchestrator.config.max_turns, 1.0)
        progress_bar.progress(progress)

        # Insert pending user message if there is one
        if st.session_state.pending_user_message:
            from agent_council.orchestrator import DiscussionTurn

            user_turn = DiscussionTurn(
                turn_number=orchestrator.current_turn + 0.1,
                agent_name="You",
                persona="Human",
                content=st.session_state.pending_user_message,
            )
            st.session_state.turns.append(user_turn)
            orchestrator.turns.append(user_turn)
            orchestrator._broadcast_turn(user_turn)

            # Clear the pending message
            st.session_state.pending_user_message = None
            # Trigger next turn immediately
            st.session_state.trigger_next_turn = True

        # Check if done
        if not orchestrator._should_continue():
            # Generate summary
            st.session_state.summary = orchestrator._generate_summary_sync()
            st.session_state.transcript_file = orchestrator._save_transcript()
            st.session_state.running = False
            # Save final session state
            save_session_state()
            del st.session_state.orchestrator
        else:
            # Auto-save session after each turn
            save_session_state()

        # Check if we should trigger next turn immediately (after user message)
        if st.session_state.trigger_next_turn:
            st.session_state.trigger_next_turn = False
            # Don't wait, trigger next turn immediately
            st.rerun()

        # Rerun to show new message
        st.rerun()

    # Format token count and segment info
    tokens = getattr(orchestrator, 'total_tokens_used', 0)
    if tokens >= 1000:
        tokens_str = f"{tokens / 1000:.1f}k"
    else:
        tokens_str = str(tokens)

    current_seg = getattr(orchestrator, 'current_segment', 0) + 1
    total_segs = len(getattr(orchestrator, 'segments', [1]))

    status_text.text(
        f"Turn {orchestrator.current_turn}/{orchestrator.config.max_turns} | Segment {current_seg}/{total_segs} | Tokens: {tokens_str}"
    )


# Display summary
if st.session_state.summary:
    summary = st.session_state.summary

    st.divider()
    st.header("📊 Results")

    cols = st.columns(5)
    with cols[0]:
        st.metric("Total Turns", summary.total_turns)
    with cols[1]:
        st.metric("Duration", str(summary.end_time - summary.start_time).split(".")[0])
    with cols[2]:
        st.metric("Consensus", "✅ Yes" if summary.consensus_reached else "❌ No")
    with cols[3]:
        st.metric("Action Items", len(summary.action_items))
    with cols[4]:
        # Get token count from orchestrator if available
        tokens = 0
        if "orchestrator" in st.session_state and hasattr(st.session_state.orchestrator, 'total_tokens_used'):
            tokens = st.session_state.orchestrator.total_tokens_used
        elif hasattr(st.session_state, 'config') and st.session_state.config:
            # Try to load from saved state
            tokens = getattr(st.session_state, 'total_tokens', 0)
        if tokens >= 1000:
            tokens_str = f"{tokens / 1000:.1f}k"
        else:
            tokens_str = str(tokens)
        st.metric("Tokens Used", tokens_str)

    cols = st.columns(2)
    with cols[0]:
        st.subheader("Key Points")
        for point in summary.key_points:
            st.markdown(f"- {point}")

        if summary.disagreements:
            st.subheader("Disagreements")
            for d in summary.disagreements:
                st.markdown(f"- ⚠️ {d}")

    with cols[1]:
        if summary.action_items:
            st.subheader("Action Items")
            for item in summary.action_items:
                st.markdown(f"- [ ] {item}")

    st.subheader("Final Recommendation")
    st.info(summary.final_recommendation or "No recommendation provided")

    # Download
    if hasattr(st.session_state, "transcript_file"):
        with open(st.session_state.transcript_file, "r") as f:
            st.download_button(
                "📥 Download Transcript",
                data=f.read(),
                file_name=st.session_state.transcript_file,
                mime="application/json",
            )

    # New discussion
    if st.button("🔄 New Discussion", use_container_width=True):
        st.session_state.running = False
        st.session_state.turns = []
        st.session_state.summary = None
        st.session_state.config = None
        st.rerun()
