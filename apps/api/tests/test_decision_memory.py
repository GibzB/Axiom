import uuid

import pytest

from conftest import FakeCursor, fake_connect
from src.services import decision_memory

PARSED_DECISION = {
    "title": "Host Atlas on Render",
    "statement": "Atlas is hosted on Render.",
    "rationale": "Traffic and spend are expected to stay low.",
    "confidence": 0.9,
    "assumptions": [
        {
            "statement": "Traffic stays below 10,000 requests per day.",
            "invalidation_condition": "Traffic exceeds 10,000 requests per day.",
        },
        {
            "statement": "Infrastructure spend stays below $100 per month.",
            "invalidation_condition": "Spend exceeds $100 per month.",
        },
    ],
}


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], "[]"),
        ([1, 2], "[1.0,2.0]"),
        ([0.25, -1.5], "[0.25,-1.5]"),
        (["0.5"], "[0.5]"),
    ],
)
def test_vector_literal_formats_floats(values, expected):
    assert decision_memory.vector_literal(values) == expected


@pytest.fixture
def stub_reasoning(monkeypatch):
    embedded = []

    def fake_generate_embedding(text):
        embedded.append(text)
        return [0.5] * 4

    monkeypatch.setattr(decision_memory, "extract_decision", lambda text: PARSED_DECISION)
    monkeypatch.setattr(decision_memory, "generate_embedding", fake_generate_embedding)
    return embedded


def test_create_decision_returns_new_id_and_parsed_decision(stub_reasoning, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))

    project_id = str(uuid.uuid4())
    decision_id, parsed = decision_memory.create_decision(project_id, "Host Atlas on Render.")

    assert isinstance(decision_id, uuid.UUID)
    assert parsed is PARSED_DECISION


def test_create_decision_persists_decision_assumptions_and_memory(stub_reasoning, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))

    project_id = str(uuid.uuid4())
    decision_id, _ = decision_memory.create_decision(project_id, "Host Atlas on Render.")

    decisions = cursor.statements_matching("INSERT INTO axiom.public.decisions")
    assert len(decisions) == 1
    assert decisions[0][1] == (
        decision_id,
        project_id,
        PARSED_DECISION["title"],
        PARSED_DECISION["statement"],
        PARSED_DECISION["rationale"],
        PARSED_DECISION["confidence"],
    )

    assumptions = cursor.statements_matching("INSERT INTO axiom.public.assumptions")
    assert [s[1] for s in assumptions] == [
        (decision_id, a["statement"], a["invalidation_condition"])
        for a in PARSED_DECISION["assumptions"]
    ]

    memories = cursor.statements_matching("INSERT INTO axiom.public.memory_objects")
    assert len(memories) == 1
    assert memories[0][1][0] == project_id
    assert memories[0][1][1] == decision_id
    assert memories[0][1][3] == "[0.5,0.5,0.5,0.5]"


def test_create_decision_embeds_rationale_and_assumptions(stub_reasoning, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))

    decision_memory.create_decision(str(uuid.uuid4()), "Host Atlas on Render.")

    assert stub_reasoning == [
        "Host Atlas on Render. Atlas is hosted on Render. "
        "Rationale: Traffic and spend are expected to stay low.. "
        "Assumption: Traffic stays below 10,000 requests per day.. "
        "Assumption: Infrastructure spend stays below $100 per month.."
    ]
    memories = cursor.statements_matching("INSERT INTO axiom.public.memory_objects")
    assert memories[0][1][2] == stub_reasoning[0]


DECISION_ID = uuid.uuid4()
ASSUMPTION_ID = uuid.uuid4()


def observation_cursor():
    return FakeCursor(
        {
            "SELECT entity_id": [(DECISION_ID,)],
            "SELECT id, statement": [
                (ASSUMPTION_ID, "Traffic stays below 10,000 requests per day.")
            ],
        }
    )


@pytest.fixture
def stub_embedding(monkeypatch):
    monkeypatch.setattr(decision_memory, "generate_embedding", lambda text: [0.25, 0.75])


def stub_evaluation(monkeypatch, evaluation):
    monkeypatch.setattr(
        decision_memory,
        "evaluate_assumption",
        lambda assumption, observation: dict(evaluation),
    )


def test_process_observation_persists_observation_and_searches_by_vector(
    stub_embedding, monkeypatch
):
    cursor = observation_cursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))
    stub_evaluation(monkeypatch, {"verdict": "SUPPORTS", "confidence": 0.7, "explanation": "ok"})

    project_id = str(uuid.uuid4())
    decision_memory.process_observation(project_id, "Atlas is receiving 47,000 requests per day.")

    inserts = cursor.statements_matching("INSERT INTO axiom.public.observations")
    assert len(inserts) == 1
    assert inserts[0][1][1:] == (project_id, "Atlas is receiving 47,000 requests per day.")

    searches = cursor.statements_matching("ORDER BY embedding <=> %s::VECTOR")
    assert len(searches) == 1
    assert searches[0][1] == (project_id, "[0.25,0.75]")


def test_process_observation_returns_evaluation_per_assumption(stub_embedding, monkeypatch):
    cursor = observation_cursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))
    stub_evaluation(
        monkeypatch,
        {"verdict": "WEAKENS", "confidence": 0.85, "explanation": "Spend is trending up."},
    )

    results = decision_memory.process_observation(str(uuid.uuid4()), "Spend is now $180 a month.")

    assert results == [
        {
            "decision_id": str(DECISION_ID),
            "assumption": "Traffic stays below 10,000 requests per day.",
            "verdict": "WEAKENS",
            "confidence": 0.85,
            "explanation": "Spend is trending up.",
        }
    ]
    evaluations = cursor.statements_matching("INSERT INTO axiom.public.assumption_evaluations")
    assert len(evaluations) == 1
    assert evaluations[0][1][0] == ASSUMPTION_ID
    assert evaluations[0][1][2:] == ("WEAKENS", 0.85, "Spend is trending up.")


def test_process_observation_skips_unrelated_evidence(stub_embedding, monkeypatch):
    cursor = observation_cursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))
    stub_evaluation(
        monkeypatch,
        {"verdict": "UNRELATED", "confidence": 0.99, "explanation": "Different topic."},
    )

    results = decision_memory.process_observation(str(uuid.uuid4()), "The office moved floors.")

    assert results == []
    assert cursor.statements_matching("INSERT INTO axiom.public.assumption_evaluations") == []
    assert cursor.statements_matching("SET status='AT_RISK'") == []


def test_process_observation_marks_decision_at_risk_on_confident_invalidation(
    stub_embedding, monkeypatch
):
    cursor = observation_cursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))
    stub_evaluation(
        monkeypatch,
        {"verdict": "INVALIDATES", "confidence": 0.8, "explanation": "Traffic is 4.7x the cap."},
    )

    decision_memory.process_observation(str(uuid.uuid4()), "47,000 requests per day.")

    updates = cursor.statements_matching("SET status='AT_RISK'")
    assert len(updates) == 1
    assert updates[0][1] == (DECISION_ID,)


def test_process_observation_keeps_decision_active_on_low_confidence_invalidation(
    stub_embedding, monkeypatch
):
    cursor = observation_cursor()
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))
    stub_evaluation(
        monkeypatch,
        {"verdict": "INVALIDATES", "confidence": 0.79, "explanation": "Unclear signal."},
    )

    results = decision_memory.process_observation(str(uuid.uuid4()), "Traffic may have grown.")

    assert len(results) == 1
    assert cursor.statements_matching("SET status='AT_RISK'") == []


def test_process_observation_returns_nothing_without_relevant_memory(
    stub_embedding, monkeypatch
):
    cursor = FakeCursor({"SELECT entity_id": []})
    monkeypatch.setattr(decision_memory.psycopg, "connect", fake_connect(cursor))

    def unreachable(assumption, observation):
        raise AssertionError("Bedrock must not be called without candidate memories.")

    monkeypatch.setattr(decision_memory, "evaluate_assumption", unreachable)

    assert decision_memory.process_observation(str(uuid.uuid4()), "New evidence.") == []
