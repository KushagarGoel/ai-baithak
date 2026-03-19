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

    # Save session data
    session_data = {
        "session_id": st.session_state.session_id,
        "turns": st.session_state.turns,
        "config": st.session_state.config,
        "summary": st.session_state.summary,
        "running": st.session_state.running,
    }

    with open(session_file, "wb") as f:
        pickle.dump(session_data, f)

    return session_file


def load_session_state(session_file: str):
    """Load session from disk."""
    with open(session_file, "rb") as f:
        session_data = pickle.load(f)

    st.session_state.session_id = session_data["session_id"]
    st.session_state.turns = session_data["turns"]
    st.session_state.config = session_data["config"]
    st.session_state.summary = session_data["summary"]
    st.session_state.running = session_data.get("running", False)

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
                sessions.append(
                    {
                        "file": filepath,
                        "id": session_data.get("session_id", filename),
                        "topic": session_data.get("config", {}).topic
                        if session_data.get("config")
                        else "Unknown",
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
    max_time = st.slider("Max Duration (minutes)", 1, 30, 5)

    st.divider()

    # Agent Assignment
    st.subheader("Assign Personas to Models")
    st.markdown("Enter your LiteLLM model names and select personas:")

    # Dynamic agent rows
    if "agent_rows" not in st.session_state:
        st.session_state.agent_rows = 3

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
        cols = st.columns([2, 2])
        with cols[0]:
            model = st.selectbox(
                f"Model {i + 1}",
                options=available_models,
                key=f"model_{i}",
            )
        with cols[1]:
            persona = st.selectbox(
                f"Persona {i + 1}",
                options=list(persona_labels.keys()),
                format_func=lambda x: persona_labels[x],
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
    orchestrator_model = st.text_input(
        "Orchestrator Model",
        value="claude-3-haiku",
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
    cols = st.columns(3)
    with cols[0]:
        st.metric("Agents", len(agent_configs))
    with cols[1]:
        st.metric("Max Duration", f"{max_time} min")
    with cols[2]:
        st.metric("Models", len(set(m for m, _ in agent_configs)))

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
        )

        st.session_state.config = config
        st.session_state.running = True
        st.session_state.turns = []
        st.rerun()


# Display discussion area
st.header("💬 Discussion")
chat_container = st.container()

# Show existing turns
with chat_container:
    for turn in st.session_state.turns:
        render_message(turn)

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

            return turn

        # Run one turn
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            turn = loop.run_until_complete(run_single_turn())
            if turn:
                st.session_state.turns.append(turn)
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

    status_text.text(
        f"Turn {orchestrator.current_turn}/{orchestrator.config.max_turns} complete"
    )


# Display summary
if st.session_state.summary:
    summary = st.session_state.summary

    st.divider()
    st.header("📊 Results")

    cols = st.columns(4)
    with cols[0]:
        st.metric("Total Turns", summary.total_turns)
    with cols[1]:
        st.metric("Duration", str(summary.end_time - summary.start_time).split(".")[0])
    with cols[2]:
        st.metric("Consensus", "✅ Yes" if summary.consensus_reached else "❌ No")
    with cols[3]:
        st.metric("Action Items", len(summary.action_items))

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
