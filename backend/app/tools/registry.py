"""Tool schemas (Anthropic tool-use format) and the dispatch table."""

from . import fixtures, knowledge, simulator

TOOL_SCHEMAS = [
    {
        "name": "get_fixtures",
        "description": (
            "Get 2026 World Cup fixtures and results in a date window. "
            "Defaults to yesterday through three days ahead. Includes live "
            "and finished scores, stage, group, and venue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                "team": {
                    "type": "string",
                    "description": "Optional team name filter",
                },
            },
        },
    },
    {
        "name": "simulate_match",
        "description": (
            "Run a Dixon-Coles simulation of a match between two of the 48 "
            "qualified teams. Returns win/draw/loss probabilities, expected "
            "goals, over/under, and most likely scorelines. First team "
            "listed is treated as the designated home side."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "home_team": {"type": "string"},
                "away_team": {"type": "string"},
            },
            "required": ["home_team", "away_team"],
        },
    },
    {
        "name": "search_knowledge",
        "description": (
            "Semantic search over the World Cup knowledge base: the 12 "
            "groups and all 48 teams, tournament format and advancement "
            "rules, the 16 venues, and historical champions/records."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
    },
]


async def dispatch_tool(name: str, tool_input: dict) -> dict:
    try:
        if name == "get_fixtures":
            return await fixtures.get_fixtures(**tool_input)
        if name == "simulate_match":
            return simulator.simulate_match(**tool_input)
        if name == "search_knowledge":
            return knowledge.search_knowledge(**tool_input)
        return {"error": f"Unknown tool: {name}"}
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
