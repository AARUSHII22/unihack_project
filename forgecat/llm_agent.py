from __future__ import annotations

import json
import os
import re
from typing import Any

from forgecat.config import LLM_MODEL, LLM_PROVIDER, MASTER_PROMPT_PATH


def _load_system_prompt() -> str:
    text = MASTER_PROMPT_PATH.read_text(encoding="utf-8")
    match = re.search(r"```\nSYSTEM PROMPT\n(.*?)```", text, re.S)
    return match.group(1).strip() if match else text


def llm_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))


def enrich_with_llm(
    raw_row: dict[str, Any],
    candidate_data: dict[str, Any],
    field_rules: str,
) -> dict[str, Any] | None:
    if not llm_available():
        return None

    system_prompt = _load_system_prompt()
    user_message = json.dumps(
        {
            "RAW_ROW": raw_row,
            "CANDIDATE_DATA": candidate_data,
            "FIELD_RULES": field_rules,
        },
        indent=2,
    )

    try:
        if LLM_PROVIDER == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            import anthropic

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text
        elif os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI

            client = OpenAI()
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or "{}"
        else:
            return None

        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception:
        return None
