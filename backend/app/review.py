import json
import os
import sys

import anthropic

PROMPT = "Review this project plan. Reply with JSON holding deadline_day, tasks and findings."


def review_plan(text, client=None):
    client = client or anthropic.Anthropic()
    reply = client.messages.create(
        model=os.environ.get("REVIEW_MODEL", "claude-sonnet-5-5"),
        max_tokens=16000,
        messages=[{"role": "user", "content": PROMPT + "\n\n" + text}],
    )
    return json.loads("".join(block.text for block in reply.content if block.type == "text"))


if __name__ == "__main__":
    plan_path, out_path = sys.argv[1], sys.argv[2]
    with open(plan_path) as f:
        review = review_plan(f.read())
    with open(out_path, "w") as f:
        json.dump(review, f, indent=2)
