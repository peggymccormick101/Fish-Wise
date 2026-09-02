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
