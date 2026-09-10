import json

import pytest

from src.services import reasoning


class FakeBedrockClient:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"output": {"message": {"content": [{"text": self.text}]}}}


@pytest.mark.parametrize(
    "text",
    [
        '{"verdict": "SUPPORTS"}',
        '  {"verdict": "SUPPORTS"}  ',
        '```json\n{"verdict": "SUPPORTS"}\n```',
        '```\n{"verdict": "SUPPORTS"}\n```',
        '```json\n{"verdict": "SUPPORTS"}\n```\n',
    ],
)
def test_json_from_text_unwraps_model_formatting(text):
    assert reasoning._json_from_text(text) == {"verdict": "SUPPORTS"}


def test_json_from_text_rejects_non_json():
    with pytest.raises(json.JSONDecodeError):
        reasoning._json_from_text("I cannot answer that.")


def test_invoke_json_returns_parsed_model_output(monkeypatch):
    fake = FakeBedrockClient('{"confidence": 0.85}')
    monkeypatch.setattr(reasoning, "client", fake)

    assert reasoning.invoke_json("system", "user") == {"confidence": 0.85}


def test_invoke_json_uses_deterministic_inference_config(monkeypatch):
    fake = FakeBedrockClient("{}")
    monkeypatch.setattr(reasoning, "client", fake)

    reasoning.invoke_json("system prompt", "user prompt")

    assert fake.calls == [
        {
            "modelId": reasoning.MODEL_ID,
            "system": [{"text": "system prompt"}],
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "user prompt"}],
                }
            ],
            "inferenceConfig": {"temperature": 0, "maxTokens": 1500},
        }
    ]


@pytest.fixture
def prompts(monkeypatch):
    captured = {}

    def fake_invoke_json(system_prompt, user_prompt):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return {"ok": True}

    monkeypatch.setattr(reasoning, "invoke_json", fake_invoke_json)
    return captured


def test_extract_decision_passes_raw_text_as_user_prompt(prompts):
    assert reasoning.extract_decision("Host Atlas on Render.") == {"ok": True}

    assert prompts["user"] == "Host Atlas on Render."
    assert "decision extraction engine" in prompts["system"]
    for key in ("title", "statement", "rationale", "confidence", "assumptions"):
        assert f'"{key}"' in prompts["system"]


def test_evaluate_assumption_includes_assumption_and_observation(prompts):
    assert reasoning.evaluate_assumption(
        "Traffic stays below 10,000 requests per day.",
        "Atlas is now receiving 47,000 requests per day.",
    ) == {"ok": True}

    assert "ASSUMPTION:\nTraffic stays below 10,000 requests per day." in prompts["user"]
    assert "NEW OBSERVATION:\nAtlas is now receiving 47,000 requests per day." in prompts["user"]


def test_evaluate_assumption_system_prompt_lists_allowed_verdicts(prompts):
    reasoning.evaluate_assumption("assumption", "observation")

    for verdict in ("SUPPORTS", "WEAKENS", "CONTRADICTS", "INVALIDATES", "UNRELATED"):
        assert verdict in prompts["system"]
