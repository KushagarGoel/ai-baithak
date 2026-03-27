"""Agent implementation using LiteLLM."""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from litellm import completion

from app.core.personas import Persona, get_persona
from app.mcp.tools import MCPToolServer, ToolResult


@dataclass
class AgentMessage:
    """A message in the conversation."""
    role: str
    content: str
    agent_name: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_results: Optional[list] = None


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    model: str
    persona: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools_enabled: bool = True


class CouncilAgent:
    """An agent in the council."""

    def __init__(
        self,
        config: AgentConfig,
        tool_server: MCPToolServer,
        litellm_proxy: Optional[Any] = None,
    ):
        self.config = config
        self.persona = get_persona(config.persona)
        self.tool_server = tool_server
        self.litellm_proxy = litellm_proxy
        self.messages: list[AgentMessage] = []
        self.tokens_used = 0
        self._stop_requested = False
        self._setup_system_message()

    def stop(self):
        """Request the agent to stop processing."""
        self._stop_requested = True

    def _setup_system_message(self):
        """Initialize with system message."""
        tools_desc = ""
        if self.config.tools_enabled:
            tools_desc = f"""

You have access to the following tools:
{self.tool_server.get_tools_description()}

To use a tool, respond with a JSON object:
{{"tool_calls": [{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}]}}
"""

        system_content = f"""{self.persona.system_prompt}

You are participating in a council discussion with other AI agents.
Your name in this discussion is: {self.config.name}

Discussion rules:
1. Stay in character based on your persona
2. Respond to the actual points raised by others
3. Be constructive but authentic to your personality
4. Use tools when you need information
5. Keep responses concise (2-4 sentences usually)
{tools_desc}
"""

        self.messages.append(AgentMessage(role="system", content=system_content, agent_name=self.config.name))

    def add_message(self, role: str, content: str, agent_name: Optional[str] = None):
        """Add a message to the conversation history."""
        self.messages.append(AgentMessage(role=role, content=content, agent_name=agent_name))

    def get_litellm_messages(self) -> list[dict]:
        """Convert messages to LiteLLM format."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    async def think_and_respond(self, context: str, max_tool_iterations: int = 10, progress_callback: Callable = None) -> dict:
        """Process context and generate a response."""
        self.add_message("user", context)

        iteration = 0
        final_response = None
        all_tool_calls = []
        all_tool_results = []

        while iteration < max_tool_iterations:
            iteration += 1

            # Check if stop was requested
            if self._stop_requested:
                print(f"[AGENT] {self.config.name} stopping due to request")
                return {
                    "agent_name": self.config.name,
                    "persona": self.persona.name,
                    "content": "[Discussion stopped by user]",
                    "tool_calls": all_tool_calls,
                    "tool_results": all_tool_results,
                    "tokens_used": self.tokens_used,
                }

            try:
                # Notify LLM call starting
                if progress_callback:
                    await progress_callback("llm_call", {"iteration": iteration})

                # Determine model format
                if self.litellm_proxy and not self.config.model.startswith("openai/"):
                    model = f"openai/{self.config.model}"
                else:
                    model = self.config.model

                completion_kwargs = {
                    "model": model,
                    "messages": self.get_litellm_messages(),
                    "temperature": self.config.temperature or self.persona.temperature,
                    "max_tokens": self.config.max_tokens or self.persona.max_tokens or 1024,
                }

                if self.litellm_proxy:
                    completion_kwargs["api_base"] = self.litellm_proxy.api_base
                    completion_kwargs["api_key"] = self.litellm_proxy.api_key

                response = completion(**completion_kwargs)
                content = response.choices[0].message.content or ""

                # Track tokens
                if hasattr(response, 'usage') and response.usage:
                    self.tokens_used += response.usage.total_tokens

                # Check for tool calls
                tool_calls = self._extract_tool_calls(content)

                if tool_calls:
                    print(f"[AGENT DEBUG] {self.config.name} extracted {len(tool_calls)} tool calls")
                    # Notify about tool calls
                    if progress_callback:
                        await progress_callback("tool_calls", {"calls": tool_calls})

                    # Execute tools and accumulate results
                    print(f"[AGENT DEBUG] Executing tool calls...")
                    tool_results = await self._execute_tool_calls(tool_calls)
                    print(f"[AGENT DEBUG] Tool execution complete: {len(tool_results)} results")
                    for i, tr in enumerate(tool_results):
                        print(f"[AGENT DEBUG] Tool {i}: {tr.get('tool')} - success={tr.get('success')}, error={tr.get('error')}")

                    all_tool_calls.extend(tool_calls)
                    all_tool_results.extend(tool_results)

                    # Notify about tool results
                    if progress_callback:
                        await progress_callback("tool_results", {"results": tool_results})

                    self.add_message("assistant", content, self.config.name)

                    # Add tool results
                    tool_result_text = self._format_tool_results(tool_results)
                    print(f"[AGENT DEBUG] Tool result text length: {len(tool_result_text)} chars")
                    self.add_message("user", f"Tool results:\n{tool_result_text}")
                    continue
                else:
                    final_response = {
                        "agent_name": self.config.name,
                        "persona": self.persona.name,
                        "content": content,
                        "tool_calls": all_tool_calls,
                        "tool_results": all_tool_results,
                        "tokens_used": getattr(response, 'usage', {}).get('total_tokens', 0),
                    }
                    self.add_message("assistant", content, self.config.name)
                    break

            except Exception as e:
                return {
                    "agent_name": self.config.name,
                    "persona": self.persona.name,
                    "content": f"[Error: {str(e)}]",
                    "tool_calls": all_tool_calls,
                    "tool_results": all_tool_results,
                    "error": str(e),
                }

        if final_response is None:
            final_response = {
                "agent_name": self.config.name,
                "persona": self.persona.name,
                "content": "[Maximum iterations reached]",
                "tool_calls": all_tool_calls,
                "tool_results": all_tool_results,
            }

        return final_response

    def _extract_tool_calls(self, content: str) -> list[dict]:
        """Extract tool calls from response content."""
        tool_calls = []
        try:
            pattern = r'\{\s*"tool_calls"\s*:[\s\S]*?\]\s*\}'
            match = re.search(pattern, content)
            if match:
                parsed = json.loads(match.group(0))
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
            result = await self.tool_server.execute(name, **arguments)
            results.append({
                "tool": name,
                "arguments": arguments,
                "success": result.success,
                "data": result.data,
                "error": result.error,
            })
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
        """Determine if this agent should speak."""
        import random
        return random.random() < self.persona.speak_probability

    def reset_messages(self, new_messages: list[AgentMessage]):
        """Reset message history."""
        self.messages = new_messages
