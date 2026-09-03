import json
import os
from typing import Optional

import anthropic

MODEL = "claude-sonnet-5"

_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy backend/.env.example to "
                "backend/.env and add your key."
            )
        default_headers = {}
        workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        if workspace_id:
            default_headers["anthropic-workspace-id"] = workspace_id
        _client = anthropic.Anthropic(api_key=api_key, default_headers=default_headers)
    return _client


LOOKUP_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "species": {
            "type": "array",
            "description": "3-8 fish species commonly found and fished for in this water body, ordered by how commonly they're targeted. Common names only, e.g. 'Largemouth Bass'.",
            "items": {"type": "string"},
        },
    },
    "required": ["species"],
    "additionalProperties": False,
}


def lookup_species(water_body_normalized: str) -> list[str]:
    """Ask Claude which fish species are commonly found in a given water
    body. water_body_normalized should already be a precise, geocoded
    location string (see app.location.geocode_water_body) rather than
    raw user input, so Claude isn't also guessing which real place the
    user meant.

    Claude is given a web search tool and told to ground its answer in
    it (state wildlife agency stocking/survey pages, fishing reports)
    rather than answering from memory alone, since guesses from training
    data alone are frequently wrong for smaller or less-documented water
    bodies."""
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=(
            "You are FishWise, an assistant that helps anglers find out "
            "which fish species are commonly found in a body of water. "
            "Before answering, use the web_search tool to check current, "
            "specific information about this exact body of water (state "
            "wildlife/fish & game agency stocking or survey pages, local "
            "fishing reports) rather than relying only on general "
            "knowledge. If search turns up nothing specific, fall back to "
            "your best general knowledge for that region."
        ),
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}],
        output_config={"format": {"type": "json_schema", "schema": LOOKUP_OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": f"Body of water: {water_body_normalized}"}],
    )

    text_blocks = [b.text for b in response.content if b.type == "text"]
    if not text_blocks:
        raise RuntimeError("Claude did not return a species list.")
    data = json.loads(text_blocks[-1])
    return data["species"]


TIPS_TOOL = {
    "name": "submit_fishing_tips",
    "description": "Submit fishing tips: recommended gear/bait and techniques for a species, water body, and season.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A short 2-4 sentence overview of how to approach fishing for this species in this water body during this season.",
            },
            "best_conditions": {
                "type": "string",
                "description": "Best time of day, weather, water temperature, and other conditions to fish for this species in this season.",
            },
            "gear": {
                "type": "array",
                "description": "Recommended hooks, bait/lures, line, and other gear.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "e.g. hook, bait, lure, line, rod/reel, other",
                        },
                        "name": {"type": "string"},
                        "notes": {
                            "type": "string",
                            "description": "Why this choice, sizing, color, or usage notes.",
                        },
                    },
                    "required": ["category", "name"],
                },
            },
            "techniques": {
                "type": "array",
                "description": "Ordered, concrete techniques/approaches to try.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["title", "description"],
                },
            },
        },
        "required": ["summary", "best_conditions", "gear", "techniques"],
    },
}


def generate_fishing_tips(water_body: str, species: str, season: str) -> dict:
    user_prompt = (
        f"Water body: {water_body}\n"
        f"Target species: {species}\n"
        f"Season: {season}\n\n"
        "Give practical, specific fishing advice for this species in this water "
        "body during this season: recommended hooks/bait/lures/line, and concrete "
        "techniques to try. Assume a beginner-to-intermediate angler."
    )

    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=(
            "You are FishWise, an assistant that gives anglers practical, "
            "specific fishing advice. Always respond by calling the "
            "submit_fishing_tips tool."
        ),
        tools=[TIPS_TOOL],
        tool_choice={"type": "tool", "name": "submit_fishing_tips"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_fishing_tips":
            return block.input

    raise RuntimeError("Claude did not return fishing tips.")


def answer_question(search_context: str, history: list[dict], question: str) -> str:
    client = get_client()

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": question})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=(
            "You are FishWise, an assistant helping an angler with a specific "
            "fishing search. Here is everything known about it so far (the tips "
            "you generated, and prior conversation context):\n\n" + search_context +
            "\n\nAnswer the angler's questions clearly and practically. Keep "
            "answers focused and concise unless detail is asked for."
        ),
        messages=messages,
    )

    text_parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(text_parts).strip()
