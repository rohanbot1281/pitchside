"""Pitchside eval harness.

Two layers, runnable from the repo root with `python -m evals.run_evals`:

1. Tool-selection accuracy — for each golden question, did the agent call
   every expected tool? Wrong-tool routing is the most common agent
   failure mode, so it gets measured directly.
2. Groundedness — does the final answer contain the facts the question
   demands (case-insensitive keyword assertions)? Keyword checks are
   crude but free and deterministic; pass --judge to add an LLM-judge
   pass that scores faithfulness of the answer to the tool outputs.

Requires ANTHROPIC_API_KEY. Results print as a table and write to
evals/results.json so runs can be diffed across prompt/model changes.
"""

import argparse
import asyncio
import json
from pathlib import Path

from anthropic import AsyncAnthropic

from app.agent import run_agent
from app.config import settings

GOLDEN = Path(__file__).parent / "golden.jsonl"
RESULTS = Path(__file__).parent / "results.json"

JUDGE_PROMPT = """You are grading an AI analyst's answer for faithfulness.

Question: {question}

Tool outputs the agent received:
{tool_outputs}

Agent's final answer:
{answer}

Score 1-5 (5 = every claim traceable to tool output, 1 = fabricated).
Respond with only a JSON object: {{"score": <int>, "reason": "<one sentence>"}}"""


async def run_case(case: dict) -> dict:
    tools_called: list[str] = []
    tool_outputs: list[dict] = []
    answer_parts: list[str] = []

    async for event in run_agent([{"role": "user", "content": case["question"]}]):
        if event["type"] == "tool_call":
            tools_called.append(event["name"])
        elif event["type"] == "tool_result":
            tool_outputs.append(event["output"])
        elif event["type"] == "text":
            answer_parts.append(event["delta"])

    answer = "".join(answer_parts)
    expected = set(case.get("expected_tools", []))
    tool_pass = expected.issubset(set(tools_called))

    answer_lower = answer.lower()
    missing = [
        kw for kw in case.get("must_mention", []) if kw.lower() not in answer_lower
    ]

    return {
        "id": case["id"],
        "question": case["question"],
        "tools_called": tools_called,
        "tool_selection_pass": tool_pass,
        "grounding_pass": not missing,
        "missing_keywords": missing,
        "answer": answer,
        "tool_outputs": tool_outputs,
    }


async def judge(client: AsyncAnthropic, result: dict) -> dict:
    msg = await client.messages.create(
        model=settings.model,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": JUDGE_PROMPT.format(
                    question=result["question"],
                    tool_outputs=json.dumps(result["tool_outputs"])[:6000],
                    answer=result["answer"],
                ),
            }
        ],
    )
    try:
        return json.loads(msg.content[0].text)
    except (json.JSONDecodeError, IndexError):
        return {"score": None, "reason": "judge output unparseable"}


async def main(use_judge: bool):
    cases = [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]
    results = []
    for case in cases:
        print(f"  running {case['id']} ...")
        results.append(await run_case(case))

    if use_judge:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        for r in results:
            r["judge"] = await judge(client, r)

    n = len(results)
    tool_acc = sum(r["tool_selection_pass"] for r in results) / n
    ground_acc = sum(r["grounding_pass"] for r in results) / n

    print(f"\n{'case':<28}{'tools':<8}{'grounded':<10}" + ("judge" if use_judge else ""))
    for r in results:
        row = f"{r['id']:<28}{'PASS' if r['tool_selection_pass'] else 'FAIL':<8}"
        row += f"{'PASS' if r['grounding_pass'] else 'FAIL':<10}"
        if use_judge:
            row += str(r.get("judge", {}).get("score", "-"))
        print(row)

    print(f"\nTool selection accuracy: {tool_acc:.0%}")
    print(f"Groundedness (keyword):  {ground_acc:.0%}")

    RESULTS.write_text(json.dumps(results, indent=2))
    print(f"Full results -> {RESULTS}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", action="store_true", help="add LLM-judge scoring")
    args = parser.parse_args()
    asyncio.run(main(args.judge))
