"""Pitchside agent core.

A multi-step tool-use loop around the Anthropic Messages API. The agent
decides which tools to call (live fixtures, Dixon-Coles simulator, RAG
knowledge base), executes them, feeds results back, and streams the whole
trace — text deltas, tool calls, tool results — as structured events that
the frontend renders live.
"""

import json
from datetime import date
from typing import AsyncGenerator

from anthropic import AsyncAnthropic

from .config import settings
from .tools.registry import TOOL_SCHEMAS, dispatch_tool

SYSTEM_PROMPT = """You are Pitchside, an analyst agent for the 2026 FIFA World Cup \
(June 11 – July 19, 2026, hosted by the United States, Mexico, and Canada).

Today's date is {today}. Resolve relative dates like "yesterday", "tomorrow", \
or "this weekend" from that. When asked about current or recent matches, \
prefer omitting date parameters so get_fixtures uses its default window.

You have three tools:
- get_fixtures: live/recent/upcoming match data and results
- simulate_match: a Dixon-Coles match simulator returning win/draw/loss \
probabilities and likely scorelines
- search_knowledge: a knowledge base covering groups, format, venues, and \
World Cup history

Ground every factual claim in tool output. If a question needs both live \
data and a simulation (e.g. "who wins tomorrow's match?"), chain the tools: \
fetch the fixture first, then simulate it. When you cite probabilities, \
always say they come from your simulation model, and round to whole \
percentages. The simulator only applies a host-nation boost to the United \
States, Mexico, and Canada; never claim other teams received one. If the \
knowledge base and live data conflict, trust live data. If you genuinely \
can't answer from your tools, say so plainly.

Style: sharp, conversational, like a good touchline analyst. No filler, \
no hedging boilerplate. Use the metric the fan cares about."""

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


async def run_agent(
    messages: list[dict],
    max_steps: int = 6,
) -> AsyncGenerator[dict, None]:
    """Run the agent loop, yielding structured events.

    Event types:
      {"type": "text", "delta": str}
      {"type": "tool_call", "id": str, "name": str, "input": dict}
      {"type": "tool_result", "id": str, "name": str, "output": dict}
      {"type": "done"}
    """
    convo = list(messages)
    system_prompt = SYSTEM_PROMPT.format(today=date.today().isoformat())

    for _ in range(max_steps):
        tool_calls = []
        assistant_blocks = []

        async with client.messages.stream(
            model=settings.model,
            max_tokens=1500,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=convo,
        ) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yield {"type": "text", "delta": event.delta.text}

            final = await stream.get_final_message()

        for block in final.content:
            if block.type == "text":
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                tool_calls.append(block)

        if final.stop_reason != "tool_use":
            yield {"type": "done"}
            return

        convo.append({"role": "assistant", "content": assistant_blocks})

        result_blocks = []
        for call in tool_calls:
            yield {
                "type": "tool_call",
                "id": call.id,
                "name": call.name,
                "input": call.input,
            }
            output = await dispatch_tool(call.name, call.input)
            yield {
                "type": "tool_result",
                "id": call.id,
                "name": call.name,
                "output": output,
            }
            result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(output),
                }
            )

        convo.append({"role": "user", "content": result_blocks})

    yield {"type": "done"}