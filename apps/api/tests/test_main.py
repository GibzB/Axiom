import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import FakeCursor, fake_connect
from src import main

client = TestClient(main.app)

PROJECT_ID = str(uuid.uuid4())
DECISION_ID = str(uuid.uuid4())
CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_root_advertises_service_entrypoints():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Axiom",
        "tagline": "Decisions have consequences. Axiom remembers why.",
        "docs": "/docs",
        "health": "/health",
    }


def test_health_reports_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "axiom-api"}


def test_create_project_inserts_row_and_returns_id(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(main.psycopg, "connect", fake_connect(cursor))

    response = client.post("/projects", json={"name": "Atlas", "description": "Core platform"})

    assert response.status_code == 201
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["name"] == "Atlas"
    assert body["description"] == "Core platform"

    inserts = cursor.statements_matching("INSERT INTO axiom.public.projects")
    assert len(inserts) == 1
    assert inserts[0][1][1:] == ("Atlas", "Core platform")


def test_create_project_defaults_description_to_none(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(main.psycopg, "connect", fake_connect(cursor))

    response = client.post("/projects", json={"name": "Atlas"})

    assert response.status_code == 201
    assert response.json()["description"] is None
    assert cursor.statements_matching("INSERT INTO axiom.public.projects")[0][1][2] is None


@pytest.mark.parametrize("name", ["", "A", "x" * 121])
def test_create_project_rejects_invalid_name(name):
    assert client.post("/projects", json={"name": name}).status_code == 422


def test_add_decision_returns_created_decision(monkeypatch):
    decision_id = uuid.uuid4()
    parsed = {"title": "Host Atlas on Render", "assumptions": []}
    calls = []

    def fake_create_decision(project_id, text):
        calls.append((project_id, text))
        return decision_id, parsed

    monkeypatch.setattr(main, "create_decision", fake_create_decision)

    response = client.post(
        f"/projects/{PROJECT_ID}/decisions",
        json={"text": "Host Atlas on Render because traffic stays low."},
    )

    assert response.status_code == 201
    assert response.json() == {
        "decisionId": str(decision_id),
        "status": "ACTIVE",
        "decision": parsed,
    }
    assert calls == [(PROJECT_ID, "Host Atlas on Render because traffic stays low.")]


def test_add_decision_rejects_malformed_project_id(monkeypatch):
    def unreachable(project_id, text):
        raise AssertionError("Decision processing must not start for an invalid project ID.")

    monkeypatch.setattr(main, "create_decision", unreachable)

    response = client.post("/projects/not-a-uuid/decisions", json={"text": "A" * 20})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid project ID."


@pytest.mark.parametrize("text", ["", "too short"])
def test_add_decision_rejects_short_text(text):
    response = client.post(f"/projects/{PROJECT_ID}/decisions", json={"text": text})

    assert response.status_code == 422


def test_add_decision_masks_downstream_failures(monkeypatch):
    def failing(project_id, text):
        raise KeyError("statement")

    monkeypatch.setattr(main, "create_decision", failing)

    response = client.post(f"/projects/{PROJECT_ID}/decisions", json={"text": "A" * 20})

    assert response.status_code == 500
    assert response.json()["detail"] == "Decision processing failed: KeyError"


@pytest.mark.parametrize(
    ("evaluations", "expected_at_risk"),
    [
        ([], False),
        ([{"verdict": "SUPPORTS", "confidence": 1.0}], False),
        ([{"verdict": "INVALIDATES", "confidence": 0.79}], False),
        ([{"verdict": "INVALIDATES", "confidence": 0.8}], True),
        (
            [
                {"verdict": "WEAKENS", "confidence": 0.9},
                {"verdict": "INVALIDATES", "confidence": 1.0},
            ],
            True,
        ),
    ],
)
def test_add_observation_flags_at_risk_only_on_confident_invalidation(
    evaluations, expected_at_risk, monkeypatch
):
    monkeypatch.setattr(main, "process_observation", lambda project_id, content: evaluations)

    response = client.post(
        f"/projects/{PROJECT_ID}/observations",
        json={"content": "Atlas is now receiving 47,000 requests per day."},
    )

    assert response.status_code == 201
    assert response.json() == {"evaluations": evaluations, "atRisk": expected_at_risk}


def test_add_observation_rejects_malformed_project_id():
    response = client.post("/projects/not-a-uuid/observations", json={"content": "New evidence."})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid project ID."


def test_add_observation_rejects_short_content():
    response = client.post(f"/projects/{PROJECT_ID}/observations", json={"content": "no"})

    assert response.status_code == 422


def test_add_observation_masks_downstream_failures(monkeypatch):
    def failing(project_id, content):
        raise RuntimeError("bedrock unavailable")

    monkeypatch.setattr(main, "process_observation", failing)

    response = client.post(
        f"/projects/{PROJECT_ID}/observations", json={"content": "New evidence."}
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Observation processing failed: RuntimeError"


def test_list_decisions_maps_rows_to_camel_case(monkeypatch):
    cursor = FakeCursor(
        {
            "FROM axiom.public.decisions": [
                (
                    uuid.UUID(DECISION_ID),
                    "Host Atlas on Render",
                    "Atlas is hosted on Render.",
                    "Traffic stays low.",
                    "ACTIVE",
                    0.9,
                    CREATED_AT,
                    CREATED_AT,
                )
            ]
        }
    )
    connect = fake_connect(cursor)
    monkeypatch.setattr(main.psycopg, "connect", connect)

    response = client.get(f"/projects/{PROJECT_ID}/decisions")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": DECISION_ID,
            "title": "Host Atlas on Render",
            "statement": "Atlas is hosted on Render.",
            "rationale": "Traffic stays low.",
            "status": "ACTIVE",
            "confidence": 0.9,
            "createdAt": CREATED_AT.isoformat(),
            "updatedAt": CREATED_AT.isoformat(),
        }
    ]
    assert cursor.statements_matching("WHERE project_id = %s")[0][1] == (PROJECT_ID,)
    assert connect.calls == [main.DATABASE_URL]


def test_list_decisions_returns_empty_list_without_rows(monkeypatch):
    monkeypatch.setattr(main.psycopg, "connect", fake_connect(FakeCursor()))

    response = client.get(f"/projects/{PROJECT_ID}/decisions")

    assert response.status_code == 200
    assert response.json() == []


def decision_cursor(confidence=0.9, assumption_confidence=0.7, assumptions=True):
    return FakeCursor(
        {
            "FROM axiom.public.decisions": [
                (
                    uuid.UUID(DECISION_ID),
                    uuid.UUID(PROJECT_ID),
                    "Host Atlas on Render",
                    "Atlas is hosted on Render.",
                    "Traffic stays low.",
                    "AT_RISK",
                    confidence,
                    CREATED_AT,
                    CREATED_AT,
                )
            ],
            "FROM axiom.public.assumptions": [
                (
                    uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    "Traffic stays below 10,000 requests per day.",
                    "Traffic exceeds 10,000 requests per day.",
                    "INVALIDATED",
                    assumption_confidence,
                )
            ]
            if assumptions
            else [],
        }
    )


def test_get_decision_returns_decision_with_assumptions(monkeypatch):
    monkeypatch.setattr(main.psycopg, "connect", fake_connect(decision_cursor()))

    response = client.get(f"/decisions/{DECISION_ID}")

    assert response.status_code == 200
    assert response.json() == {
        "id": DECISION_ID,
        "projectId": PROJECT_ID,
        "title": "Host Atlas on Render",
        "statement": "Atlas is hosted on Render.",
        "rationale": "Traffic stays low.",
        "status": "AT_RISK",
        "confidence": 0.9,
        "createdAt": CREATED_AT.isoformat(),
        "updatedAt": CREATED_AT.isoformat(),
        "assumptions": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "statement": "Traffic stays below 10,000 requests per day.",
                "invalidationCondition": "Traffic exceeds 10,000 requests per day.",
                "status": "INVALIDATED",
                "confidence": 0.7,
            }
        ],
    }


def test_get_decision_preserves_missing_confidence(monkeypatch):
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        fake_connect(decision_cursor(confidence=None, assumption_confidence=None)),
    )

    body = client.get(f"/decisions/{DECISION_ID}").json()

    assert body["confidence"] is None
    assert body["assumptions"][0]["confidence"] is None


def test_get_decision_returns_empty_assumptions(monkeypatch):
    monkeypatch.setattr(
        main.psycopg, "connect", fake_connect(decision_cursor(assumptions=False))
    )

    assert client.get(f"/decisions/{DECISION_ID}").json()["assumptions"] == []


def test_get_decision_returns_404_for_unknown_decision(monkeypatch):
    monkeypatch.setattr(main.psycopg, "connect", fake_connect(FakeCursor()))

    response = client.get(f"/decisions/{DECISION_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Decision not found."


def test_lambda_handler_wraps_the_asgi_app():
    assert main.handler.app is main.app
