"""Smoke test Nebius Token Factory credentials before running Rasa."""

from __future__ import annotations

import os
import sys


def main() -> int:
    api_key = os.environ.get("NEBIUS_API_KEY")
    model_id = os.environ.get("NEBIUS_MODEL_ID")
    if not api_key or not model_id:
        print("Set NEBIUS_API_KEY and NEBIUS_MODEL_ID first.")
        return 1

    try:
        from openai import OpenAI
    except ImportError:
        print("Install openai first: python -m pip install openai")
        return 1

    client = OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=api_key,
    )
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": "You are a terse health-check responder."},
            {"role": "user", "content": "Reply with: nebius ok"},
        ],
        temperature=0,
        max_tokens=20,
    )
    print(response.choices[0].message.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
