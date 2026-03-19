"""Agent implementation using LiteLLM."""

import json
from dataclasses import dataclass, field
from typing import Any, Optional
import litellm
from litellm import completion

from .personas import Persona
from .tools import ToolRegistry, ToolResult


@dataclass
class AgentMessage:
    """A message in the conversation."""

    role: str  # "system", "user", "assistant"
    content: str
    agent_name: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_results: Optional[list] = None


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    model: str  # LiteLLM model name, e.g., "openai/gpt-4", "anthropic/claude-3-opus-20240229"
    persona: str  # Persona key from personas.py
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools_enabled: bool = True


class CouncilAgent:
    """An agent in the council with a specific persona and model."""

    def __init__(
        self,
        config: AgentConfig,
        persona: Persona,
        tool_registry: ToolRegistry,
        litellm_proxy: Optional["LiteLLMProxyConfig"] = None,
    ):
        self.config = config
        self.persona = persona
        self.tool_registry = tool_registry
        self.litellm_proxy = litellm_proxy
        self.messages: list[AgentMessage] = []
        self._setup_system_message()

    def _setup_system_message(self):
        """Initialize with system message including persona and tools."""
        tools_desc = ""
        if self.config.tools_enabled:
            tools_desc = f"""

You have access to the following tools:
{self.tool_registry.get_tools_description()}

To use a tool, respond with a JSON object in this format:
{{"tool_calls": [{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}]}}

You can make multiple tool calls in one response if needed.
"""

        system_content = f"""{self.persona.system_prompt}

You are participating in a council discussion with other AI agents. Each has a different personality and expertise.
Your name in this discussion is: {self.config.name}

Discussion rules:
1. Stay in character based on your persona
2. Respond to the actual points raised by others
3. Be constructive but authentic to your personality
4. Use tools when you need information to make a point
5. Keep responses concise (2-4 sentences usually, longer when making detailed arguments)
{tools_desc}
"""

        self.messages.append(
            AgentMessage(
                role="system", content=system_content, agent_name=self.config.name
            )
        )

    def add_message(self, role: str, content: str, agent_name: Optional[str] = None):
        """Add a message to the conversation history."""
        self.messages.append(
            AgentMessage(role=role, content=content, agent_name=agent_name)
        )

    def get_litellm_messages(self) -> list[dict]:
        """Convert messages to LiteLLM format."""
        result = []
        for msg in self.messages:
            litellm_msg = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.agent_name and msg.role == "assistant":
                litellm_msg["name"] = msg.agent_name
            result.append(litellm_msg)
        return result

    async def think_and_respond(
        self, context: str, max_tool_iterations: int = 20
    ) -> dict:
        """
        Process context and generate a response, potentially using tools.

        Returns:
            dict with keys: agent_name, content, tool_calls, tool_results
        """
        # Add the context as user message
        self.add_message("user", context)

        iteration = 0
        final_response = None

        while iteration < max_tool_iterations:
            iteration += 1

            # Get completion from LiteLLM
            try:
                # Determine model format
                # When using LiteLLM proxy (OpenAI-compatible endpoint), prefix with 'openai/'
                if self.litellm_proxy and not self.config.model.startswith("openai/"):
                    model = f"openai/{self.config.model}"
                else:
                    model = self.config.model

                # Build completion kwargs
                completion_kwargs = {
                    "model": model,
                    "messages": self.get_litellm_messages(),
                    "temperature": self.config.temperature or self.persona.temperature,
                    "max_tokens": self.config.max_tokens or self.persona.max_tokens,
                }

                # Add LiteLLM proxy settings if configured
                if self.litellm_proxy:
                    completion_kwargs["api_base"] = self.litellm_proxy.api_base
                    completion_kwargs["api_key"] = self.litellm_proxy.api_key

                response = completion(**completion_kwargs)

                content = response.choices[0].message.content or ""

                # Check for tool calls in the response
                tool_calls = self._extract_tool_calls(content)

                # Debug logging
                if tool_calls:
                    print(
                        f"[DEBUG] {self.config.name} detected tool_calls: {tool_calls}"
                    )
                elif "tool" in content.lower() or "{" in content:
                    print(
                        f"[DEBUG] {self.config.name} content snippet: {content[:200]}..."
                    )

                if tool_calls:
                    # Execute tools and continue the conversation
                    print(
                        f"[DEBUG] {self.config.name} executing {len(tool_calls)} tool call(s)"
                    )
                    tool_results = await self._execute_tool_calls(tool_calls)

                    # Log results
                    for tr in tool_results:
                        status = (
                            "SUCCESS"
                            if tr["success"]
                            else f"FAILED: {tr.get('error', 'unknown')}"
                        )
                        print(f"[DEBUG] Tool '{tr['tool']}' - {status}")

                    # Add the assistant message with tool calls
                    self.add_message("assistant", content, self.config.name)

                    # Add tool results as a follow-up message
                    tool_result_text = self._format_tool_results(tool_results)
                    self.add_message("user", f"Tool results:\n{tool_result_text}")

                    # Continue to get final response
                    print(
                        f"[DEBUG] {self.config.name} iteration {iteration} complete, requesting final response"
                    )
                    continue
                else:
                    # No tool calls, this is the final response
                    print(
                        f"[DEBUG] {self.config.name} no tool calls detected, final response ready"
                    )
                    final_response = {
                        "agent_name": self.config.name,
                        "persona": self.persona.name,
                        "content": content,
                        "tool_calls": [],
                        "tool_results": [],
                    }
                    self.add_message("assistant", content, self.config.name)
                    break

            except Exception as e:
                return {
                    "agent_name": self.config.name,
                    "persona": self.persona.name,
                    "content": f"[Error generating response: {str(e)}]",
                    "tool_calls": [],
                    "tool_results": [],
                    "error": str(e),
                }

        if final_response is None:
            final_response = {
                "agent_name": self.config.name,
                "persona": self.persona.name,
                "content": "[Reached maximum tool iterations without final response]",
                "tool_calls": [],
                "tool_results": [],
            }

        return final_response

    def _extract_tool_calls(self, content: str) -> list[dict]:
        """Extract tool calls from response content."""
        tool_calls = []

        # Look for explicit tool call JSON block
        # Format: {"tool_calls": [{"name": "...", "arguments": {...}}]}
        try:
            # Find JSON that starts with {"tool_calls"
            import re

            pattern = r'\{\s*"tool_calls"\s*:[\s\S]*?\]\s*\}'
            match = re.search(pattern, content)

            if match:
                json_str = match.group(0)
                parsed = json.loads(json_str)
                if "tool_calls" in parsed and isinstance(parsed["tool_calls"], list):
                    tool_calls = parsed["tool_calls"]
        except (json.JSONDecodeError, re.error):
            pass

        return tool_calls

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """Execute tool calls and return results."""
        results = []
        for call in tool_calls:
            name = call.get("name")
            arguments = call.get("arguments", {})

            result = await self.tool_registry.execute(name, **arguments)
            results.append(
                {
                    "tool": name,
                    "arguments": arguments,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                }
            )
        return results

    def _format_tool_results(self, tool_results: list[dict]) -> str:
        """Format tool results for the conversation."""
        lines = []
        for result in tool_results:
            if result["success"]:
                lines.append(f"Tool '{result['tool']}' succeeded:")
                lines.append(json.dumps(result["data"], indent=2))
            else:
                lines.append(f"Tool '{result['tool']}' failed: {result['error']}")
        return "\n".join(lines)

    def should_speak(self) -> bool:
        """Determine if this agent should speak based on their speak probability."""
        import random

        return random.random() < self.persona.speak_probability
