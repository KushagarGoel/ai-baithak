"""Example usage of Agent Council."""

import asyncio
import os

from agent_council import CouncilOrchestrator
from agent_council.config import AgentConfig, CouncilConfig, LiteLLMProxyConfig


async def main():
    """Run a sample council discussion."""

    print("🏛️  Agent Council Example")
    print("=" * 50)

    # Example 1: Using personal LiteLLM proxy with 10 models
    print("\n1. Using LiteLLM Proxy with 10 models...")
    print("   All agents use the same proxy URL and API key, just different model names")

    # Your 10 deployed models (just the model names as configured in your LiteLLM)
    my_models = [
        "gpt-4o",           # model name in your LiteLLM
        "gpt-4o-mini",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "llama-3-70b",
        "mixtral-8x22b",
        "command-r-plus",
    ]

    # Configure LiteLLM proxy (single URL and key for all models)
    litellm_proxy = LiteLLMProxyConfig(
        api_base="http://localhost:4000",  # Your LiteLLM proxy URL
        api_key=os.getenv("LITELLM_PROXY_KEY", "your-proxy-key"),
    )

    # Create agents - same persona can be used with different models
    agents = [
        AgentConfig(name="Lazy GPT-4o", model="gpt-4o", persona="the_lazy_one"),
        AgentConfig(name="Lazy Claude", model="claude-3-haiku", persona="the_lazy_one"),  # Same persona, different model!
        AgentConfig(name="Smart Opus", model="claude-3-opus", persona="the_egomaniac"),
        AgentConfig(name="Skeptical Sonnet", model="claude-3-sonnet", persona="the_devils_advocate"),
        AgentConfig(name="Creative Gemini", model="gemini-1.5-pro", persona="the_creative"),
        AgentConfig(name="Pragmatic GPT-Mini", model="gpt-4o-mini", persona="the_pragmatist"),
        AgentConfig(name="Empath Flash", model="gemini-1.5-flash", persona="the_empath"),
        AgentConfig(name="Researcher Llama", model="llama-3-70b", persona="the_researcher"),
        AgentConfig(name="Analyst Mixtral", model="mixtral-8x22b", persona="the_devils_advocate"),
        AgentConfig(name="Advisor Cohere", model="command-r-plus", persona="the_pragmatist"),
    ]

    config = CouncilConfig(
        topic="Should we migrate our database from PostgreSQL to a distributed solution?",
        max_duration_minutes=10,
        max_turns=25,
        agents=agents[:len(my_models)],  # Use as many as you have models
        litellm_proxy=litellm_proxy,  # All agents use this same proxy
        orchestrator_model="claude-3-haiku",  # Also uses the proxy
    )

    # Example 2: Direct API (no proxy)
    print("\n2. Alternative: Direct API access...")
    print("   Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables")
    print("   Then use CouncilConfig without litellm_proxy")

    # config = CouncilConfig(
    #     topic="Your topic",
    #     agents=[
    #         AgentConfig(name="Agent1", model="openai/gpt-4o", persona="the_lazy_one"),
    #         AgentConfig(name="Agent2", model="anthropic/claude-3-haiku", persona="the_egomaniac"),
    #     ],
    #     # No litellm_proxy - uses direct API calls
    # )

    print(f"\nTopic: {config.topic}")
    print(f"Duration: {config.max_duration_minutes} minutes")
    print(f"Max turns: {config.max_turns}")
    print(f"Agents: {len(config.agents)}")
    print(f"Using LiteLLM Proxy: {config.litellm_proxy.api_base if config.litellm_proxy else 'No'}")
    for agent in config.agents:
        print(f"  - {agent.name} ({agent.persona}) -> {agent.model}")

    # Run the discussion
    print("\n3. Starting discussion...")
    print("-" * 50)

    def progress_callback(turn_num, total_turns, turn):
        print(f"\n[Turn {turn_num}/{total_turns}] {turn.agent_name} ({turn.persona}):")
        print(f"{turn.content[:200]}..." if len(turn.content) > 200 else turn.content)

    orchestrator = CouncilOrchestrator(config)
    summary = await orchestrator.run_discussion(progress_callback=progress_callback)

    # Print results
    print("\n" + "=" * 50)
    print("📋 DISCUSSION SUMMARY")
    print("=" * 50)

    print(f"\nTotal turns: {summary.total_turns}")
    print(f"Duration: {summary.end_time - summary.start_time}")
    print(f"Consensus reached: {'✅ Yes' if summary.consensus_reached else '❌ No'}")

    print("\nKey Points:")
    for point in summary.key_points:
        print(f"  • {point}")

    print("\nDisagreements:")
    if summary.disagreements:
        for d in summary.disagreements:
            print(f"  • {d}")
    else:
        print("  None")

    print("\nAction Items:")
    if summary.action_items:
        for item in summary.action_items:
            print(f"  • [ ] {item}")
    else:
        print("  None")

    print(f"\nFinal Recommendation:\n  {summary.final_recommendation}")

    # Save transcript
    transcript_file = orchestrator._save_transcript()
    print(f"\n📝 Transcript saved to: {transcript_file}")


if __name__ == "__main__":
    asyncio.run(main())
