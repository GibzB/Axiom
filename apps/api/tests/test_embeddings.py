import json

import pytest

from src.services import embeddings


class FakeBody:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()


class FakeBedrockClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        return {"body": FakeBody(self.payload)}


@pytest.fixture
def client(monkeypatch):
    fake = FakeBedrockClient({"embedding": [0.5] * embeddings.DIMENSIONS})
    monkeypatch.setattr(embeddings, "get_client", lambda: fake)
    return fake


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_generate_embedding_rejects_blank_input(text, monkeypatch):
    def unreachable():
        raise AssertionError("Bedrock must not be called for blank input.")

    monkeypatch.setattr(embeddings, "get_client", unreachable)

    with pytest.raises(ValueError, match="cannot be empty"):
        embeddings.generate_embedding(text)


def test_generate_embedding_returns_vector(client):
    vector = embeddings.generate_embedding("Host Atlas on Render.")

    assert vector == [0.5] * embeddings.DIMENSIONS


def test_generate_embedding_sends_expected_bedrock_request(client):
    embeddings.generate_embedding("  Host Atlas on Render.  ")

    assert len(client.calls) == 1
    call = client.calls[0]

    assert call["modelId"] == embeddings.MODEL_ID
    assert call["contentType"] == "application/json"
    assert call["accept"] == "application/json"
    assert json.loads(call["body"]) == {
        "inputText": "Host Atlas on Render.",
        "dimensions": embeddings.DIMENSIONS,
        "normalize": True,
    }


def test_generate_embedding_rejects_unexpected_dimensions(monkeypatch):
    fake = FakeBedrockClient({"embedding": [0.1, 0.2, 0.3]})
    monkeypatch.setattr(embeddings, "get_client", lambda: fake)

    with pytest.raises(RuntimeError, match=f"Expected {embeddings.DIMENSIONS} dimensions, got 3"):
        embeddings.generate_embedding("Host Atlas on Render.")


def test_get_client_targets_bedrock_runtime_in_configured_region(monkeypatch):
    captured = {}

    def fake_boto_client(service, region_name):
        captured["service"] = service
        captured["region_name"] = region_name
        return "client"

    monkeypatch.setattr(embeddings.boto3, "client", fake_boto_client)

    assert embeddings.get_client() == "client"
    assert captured == {
        "service": "bedrock-runtime",
        "region_name": embeddings.REGION,
    }
