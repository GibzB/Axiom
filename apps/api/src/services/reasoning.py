import json
import os
import boto3

REGION = os.getenv("AWS_REGION", "eu-west-1")
MODEL_ID = os.getenv("BEDROCK_GENERATION_MODEL_ID", "amazon.nova-2-lite-v1:0")

client = boto3.client("bedrock-runtime", region_name=REGION)


def _json_from_text(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    return json.loads(text.strip())


def invoke_json(system_prompt: str, user_prompt: str) -> dict:
    response = client.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[
            {
                "role": "user",
                "content": [{"text": user_prompt}],
            }
        ],
        inferenceConfig={
            "temperature": 0,
            "maxTokens": 1500,
        },
    )

    text = response["output"]["message"]["content"][0]["text"]
    return _json_from_text(text)


def extract_decision(text: str) -> dict:
    return invoke_json(
        """
You are Axiom's decision extraction engine.
Extract structured organizational decision memory.

Return ONLY valid JSON:
{
  "title": "short title",
  "statement": "what was decided",
  "rationale": "why",
  "confidence": 0.0,
  "assumptions": [
    {
      "statement": "...",
      "invalidation_condition": "..."
    }
  ]
}
""",
        text,
    )


def evaluate_assumption(assumption: str, observation: str) -> dict:
    return invoke_json(
        """
You are Axiom's assumption evaluation engine.

Compare historical assumptions with new evidence.

Allowed verdicts:
SUPPORTS
WEAKENS
CONTRADICTS
INVALIDATES
UNRELATED

Return ONLY valid JSON:
{
  "verdict": "VERDICT",
  "confidence": 0.0,
  "explanation": "concise explanation"
}
""",
        f"""
ASSUMPTION:
{assumption}

NEW OBSERVATION:
{observation}
""",
    )
