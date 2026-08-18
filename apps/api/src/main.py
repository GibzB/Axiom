import os
import uuid

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.services.decision_memory import create_decision, process_observation

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI(
    title="Axiom API",
    version="0.1.0",
    description="Agentic decision-memory API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class DecisionCreate(BaseModel):
    text: str = Field(min_length=10, max_length=5000)


class ObservationCreate(BaseModel):
    content: str = Field(min_length=5, max_length=5000)


@app.get("/")
def root():
    return {
        "name": "Axiom",
        "tagline": "Decisions have consequences. Axiom remembers why.",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "axiom-api"}


@app.post("/projects", status_code=201)
def create_project(payload: ProjectCreate):
    project_id = uuid.uuid4()

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO axiom.public.projects
                    (id, name, description)
                VALUES (%s, %s, %s)
                """,
                (project_id, payload.name, payload.description),
            )

    return {
        "id": str(project_id),
        "name": payload.name,
        "description": payload.description,
    }


@app.post("/projects/{project_id}/decisions", status_code=201)
def add_decision(project_id: str, payload: DecisionCreate):
    try:
        uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    try:
        decision_id, parsed = create_decision(project_id, payload.text)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Decision processing failed: {type(exc).__name__}",
        )

    return {
        "decisionId": str(decision_id),
        "status": "ACTIVE",
        "decision": parsed,
    }


@app.post("/projects/{project_id}/observations", status_code=201)
def add_observation(project_id: str, payload: ObservationCreate):
    try:
        uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    try:
        evaluations = process_observation(project_id, payload.content)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Observation processing failed: {type(exc).__name__}",
        )

    return {
        "evaluations": evaluations,
        "atRisk": any(
            e["verdict"] == "INVALIDATES" and e["confidence"] >= 0.8
            for e in evaluations
        ),
    }


@app.get("/projects/{project_id}/decisions")
def list_decisions(project_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    title,
                    statement,
                    rationale,
                    status,
                    confidence,
                    created_at,
                    updated_at
                FROM axiom.public.decisions
                WHERE project_id = %s
                ORDER BY created_at DESC
                """,
                (project_id,),
            )

            rows = cur.fetchall()

    return [
        {
            "id": str(row[0]),
            "title": row[1],
            "statement": row[2],
            "rationale": row[3],
            "status": row[4],
            "confidence": float(row[5]) if row[5] is not None else None,
            "createdAt": row[6],
            "updatedAt": row[7],
        }
        for row in rows
    ]


@app.get("/decisions/{decision_id}")
def get_decision(decision_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    project_id,
                    title,
                    statement,
                    rationale,
                    status,
                    confidence,
                    created_at,
                    updated_at
                FROM axiom.public.decisions
                WHERE id = %s
                """,
                (decision_id,),
            )

            decision = cur.fetchone()

            if not decision:
                raise HTTPException(status_code=404, detail="Decision not found.")

            cur.execute(
                """
                SELECT
                    id,
                    statement,
                    invalidation_condition,
                    status,
                    confidence
                FROM axiom.public.assumptions
                WHERE decision_id = %s
                ORDER BY created_at
                """,
                (decision_id,),
            )

            assumptions = cur.fetchall()

    return {
        "id": str(decision[0]),
        "projectId": str(decision[1]),
        "title": decision[2],
        "statement": decision[3],
        "rationale": decision[4],
        "status": decision[5],
        "confidence": float(decision[6]) if decision[6] is not None else None,
        "createdAt": decision[7],
        "updatedAt": decision[8],
        "assumptions": [
            {
                "id": str(a[0]),
                "statement": a[1],
                "invalidationCondition": a[2],
                "status": a[3],
                "confidence": float(a[4]) if a[4] is not None else None,
            }
            for a in assumptions
        ],
    }
