# Agent Council 🏛️

A multi-agent deliberation system that brings together AI agents with distinct personalities to solve complex problems through structured discussion.

## Features

- **Multiple Personas**: 8 unique agent personalities (The Lazy One, Know-It-All, Devil's Advocate, Creative, Pragmatist, Empath, Researcher, Orchestrator)
- **Tool Access**: Agents can read files, write files, search the web, and execute Python code
- **Multi-Model Support**: Use different LLMs (OpenAI, Anthropic, Google, etc.) via LiteLLM
- **Interactive Dashboard**: Visualize discussions in real-time with Streamlit
- **Time-Bound Discussions**: Set max duration and turn limits
- **Orchestrator Management**: Manager agent keeps discussions on track
- **Same Persona, Different Models**: Run multiple agents with the same personality but different LLMs

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set API Keys

```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
# Add other providers as needed
```

### 3. Run the Dashboard

```bash
streamlit run dashboard.py
```

## Usage Examples

### Programmatic Usage

```python
import asyncio
from agent_council import CouncilConfig, CouncilOrchestrator
from agent_council.config import AgentConfig

async def main():
    # Configure the council
    config = CouncilConfig(
        topic="Should we adopt microservices architecture?",
        max_duration_minutes=10,
        max_turns=20,
        agents=[
            AgentConfig(name="Lazy Larry", model="openai/gpt-4o-mini", persona="the_lazy_one"),
            AgentConfig(name="Smart Sally", model="anthropic/claude-3-haiku-20240307", persona="the_egomaniac"),
            AgentConfig(name="Skeptical Sam", model="openai/gpt-4o-mini", persona="the_devils_advocate"),
            AgentConfig(name="Creative Casey", model="anthropic/claude-3-haiku-20240307", persona="the_creative"),
            AgentConfig(name="Practical Pat", model="openai/gpt-4o-mini", persona="the_pragmatist"),
        ]
    )

    # Run discussion
    orchestrator = CouncilOrchestrator(config)
    summary = await orchestrator.run_discussion()

    # Print results
    print(f"Consensus: {summary.consensus_reached}")
    print(f"Key Points: {summary.key_points}")
    print(f"Recommendation: {summary.final_recommendation}")

asyncio.run(main())
```

### Using 3-6 Different Models

```python
models = [
    "openai/gpt-4o",
    "anthropic/claude-3-sonnet-20240229",
    "openai/gpt-4o-mini",
    "anthropic/claude-3-haiku-20240307",
    "google/gemini-1.5-flash",
]

config = CouncilConfig.create_with_models(
    topic="How to optimize our database queries?",
    models=models,
    max_duration_minutes=15,
)
```

## Agent Personas

| Persona | Description | Strengths |
|---------|-------------|-----------|
| **The Lazy One** | Always seeks the easiest solution | Identifies unnecessary complexity, finds shortcuts |
| **The Know-It-All** | Confident expert, often right but arrogant | Brings advanced knowledge, challenges weak ideas |
| **Devil's Advocate** | Questions everything | Prevents groupthink, finds failure modes |
| **The Creative** | Thinks outside the box | Novel solutions, lateral thinking |
| **The Pragmatist** | Focused on what works | Implementation details, resource constraints |
| **The Empath** | Considers human impact | UX, ethics, team dynamics |
| **The Researcher** | Evidence-based | Fact-checking, precedents, data |
| **The Orchestrator** | Facilitates and summarizes | Keeps discussion on track |

## Available Tools

Agents can use these tools during discussions:

- `read_file(path)` - Read file contents
- `write_file(path, content)` - Write to files
- `list_directory(path)` - List directory contents
- `web_search(query)` - Search the web via DuckDuckGo
- `web_fetch(url)` - Fetch web page content
- `execute_python(code)` - Execute Python code

## Model Support

Any model supported by [LiteLLM](https://docs.litellm.ai/docs/providers) works:

- OpenAI (`openai/gpt-4o`, `openai/gpt-4o-mini`)
- Anthropic (`anthropic/claude-3-opus-20240229`, `anthropic/claude-3-sonnet-20240229`, `anthropic/claude-3-haiku-20240307`)
- Google (`google/gemini-1.5-pro`, `google/gemini-1.5-flash`)
- Azure, AWS Bedrock, Cohere, Mistral, and more

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CouncilOrchestrator                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  CouncilAgent│  │  CouncilAgent│  │  CouncilAgent│         │
│  │  (Lazy)      │  │  (Smart)     │  │  (Skeptic)   │         │
│  │  GPT-4o-mini │  │  Claude      │  │  GPT-4o-mini │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                  │
│                   ┌──────┴──────┐                          │
│                   │  Discussion │                          │
│                   │  Engine     │                          │
│                   └──────┬──────┘                          │
│                          │                                  │
│                   ┌──────┴──────┐                          │
│                   │Orchestrator │                          │
│                   │(Manager)    │                          │
│                   └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Options

```python
CouncilConfig(
    topic="Your discussion topic",
    max_duration_minutes=10,      # Max time to run
    max_turns=20,                 # Max discussion turns
    min_turns=5,                  # Min turns before early termination
    orchestrator_frequency=3,     # Interject every N turns
    save_transcript=True,         # Save to file
    workspace_path=".",           # Base path for file tools
)
```

## Example Use Cases

1. **Technical Architecture Decisions**: "Should we use Redis or Memcached for caching?"
2. **Product Strategy**: "What's the best monetization strategy for our freemium product?"
3. **Code Review**: "Review this PR for potential issues and improvements"
4. **Research Synthesis**: "What are the pros and cons of different ML approaches?"
5. **Creative Brainstorming**: "Generate ideas for our next marketing campaign"

## License

MIT
