import json
import os

import boto3


MODEL_ID = os.getenv(
    "BEDROCK_EMBEDDING_MODEL_ID",
    "amazon.titan-embed-text-v2:0",
)
REGION = os.getenv("AWS_REGION", "eu-west-1")
DIMENSIONS = int(os.getenv("BEDROCK_EMBEDDING_DIMENSIONS", "1024"))


def get_client():
    return boto3.client("bedrock-runtime", region_name=REGION)


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Embedding input cannot be empty.")

    response = get_client().invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "inputText": text.strip(),
                "dimensions": DIMENSIONS,
                "normalize": True,
            }
        ),
    )

    payload = json.loads(response["body"].read())
    embedding = payload["embedding"]

    if len(embedding) != DIMENSIONS:
        raise RuntimeError(
            f"Expected {DIMENSIONS} dimensions, got {len(embedding)}"
        )

    return embedding
