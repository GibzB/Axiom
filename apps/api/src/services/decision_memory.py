import os
import uuid
import psycopg

from src.services.embeddings import generate_embedding
from src.services.reasoning import extract_decision, evaluate_assumption

DATABASE_URL = os.environ["DATABASE_URL"]


def vector_literal(values):
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def create_decision(project_id: str, text: str):
    parsed = extract_decision(text)
    decision_id = uuid.uuid4()

    memory_text = (
        f"{parsed['title']}. {parsed['statement']} "
        f"Rationale: {parsed['rationale']}. "
        + " ".join(
            f"Assumption: {a['statement']}."
            for a in parsed["assumptions"]
        )
    )

    embedding = generate_embedding(memory_text)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                INSERT INTO axiom.public.decisions
                (id, project_id, title, statement, rationale, status, confidence)
                VALUES (%s,%s,%s,%s,%s,'ACTIVE',%s)
            """, (
                decision_id,
                project_id,
                parsed["title"],
                parsed["statement"],
                parsed["rationale"],
                parsed["confidence"],
            ))

            for assumption in parsed["assumptions"]:
                cur.execute("""
                    INSERT INTO axiom.public.assumptions
                    (decision_id, statement, invalidation_condition)
                    VALUES (%s,%s,%s)
                """, (
                    decision_id,
                    assumption["statement"],
                    assumption["invalidation_condition"],
                ))

            cur.execute("""
                INSERT INTO axiom.public.memory_objects
                (project_id, entity_type, entity_id,
                 memory_type, content, embedding)
                VALUES (%s,'DECISION',%s,'DECISION_MEMORY',
                        %s,%s::VECTOR)
            """, (
                project_id,
                decision_id,
                memory_text,
                vector_literal(embedding),
            ))

    return decision_id, parsed


def process_observation(project_id: str, content: str):
    observation_id = uuid.uuid4()
    query_embedding = generate_embedding(content)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                INSERT INTO axiom.public.observations
                (id, project_id, content)
                VALUES (%s,%s,%s)
            """, (observation_id, project_id, content))

            cur.execute("""
                SELECT entity_id
                FROM axiom.public.memory_objects
                WHERE project_id=%s
                  AND entity_type='DECISION'
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::VECTOR
                LIMIT 5
            """, (
                project_id,
                vector_literal(query_embedding),
            ))

            candidates = [row[0] for row in cur.fetchall()]

            results = []

            for decision_id in candidates:

                cur.execute("""
                    SELECT id, statement
                    FROM axiom.public.assumptions
                    WHERE decision_id=%s
                """, (decision_id,))

                for assumption_id, statement in cur.fetchall():

                    evaluation = evaluate_assumption(
                        statement,
                        content
                    )

                    if evaluation["verdict"] == "UNRELATED":
                        continue

                    cur.execute("""
                        INSERT INTO axiom.public.assumption_evaluations
                        (assumption_id, observation_id,
                         verdict, confidence, explanation)
                        VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (assumption_id, observation_id)
                        DO NOTHING
                    """, (
                        assumption_id,
                        observation_id,
                        evaluation["verdict"],
                        evaluation["confidence"],
                        evaluation["explanation"],
                    ))

                    if (
                        evaluation["verdict"] == "INVALIDATES"
                        and evaluation["confidence"] >= 0.8
                    ):
                        cur.execute("""
                            UPDATE axiom.public.decisions
                            SET status='AT_RISK',
                                updated_at=now()
                            WHERE id=%s
                        """, (decision_id,))

                    results.append({
                        "decision_id": str(decision_id),
                        "assumption": statement,
                        **evaluation,
                    })

    return results
