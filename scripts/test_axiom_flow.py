import os
import sys
import uuid

import psycopg

sys.path.insert(0, "apps/api")

from src.services.decision_memory import create_decision, process_observation


DATABASE_URL = os.environ["DATABASE_URL"]


def create_project():
    project_id = uuid.uuid4()

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO axiom.public.projects
                    (id, name, description)
                VALUES (%s, %s, %s)
                """,
                (
                    project_id,
                    "Atlas Labs",
                    "Axiom end-to-end decision-memory demo",
                ),
            )

    return project_id


def get_decision(decision_id):
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
                    confidence
                FROM axiom.public.decisions
                WHERE id = %s
                """,
                (decision_id,),
            )

            return cur.fetchone()


def get_assumptions(decision_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    statement,
                    invalidation_condition,
                    status
                FROM axiom.public.assumptions
                WHERE decision_id = %s
                ORDER BY created_at
                """,
                (decision_id,),
            )

            return cur.fetchall()


def main():
    print("\n========================================")
    print("AXIOM END-TO-END AGENTIC MEMORY TEST")
    print("========================================\n")

    project_id = create_project()

    decision_text = """
    We decided to host Atlas on Render because we expect fewer than
    10,000 requests per day and want to keep infrastructure spending
    below $100 per month.
    """

    print("1. Capturing decision...")

    decision_id, parsed = create_decision(
        str(project_id),
        decision_text,
    )

    decision = get_decision(decision_id)

    print("\nDecision stored:")
    print("ID:", decision[0])
    print("Title:", decision[1])
    print("Status:", decision[4])

    assert decision[4] == "ACTIVE", (
        f"Expected ACTIVE, got {decision[4]}"
    )

    print("\n2. Persistent assumptions:")

    assumptions = get_assumptions(decision_id)

    for assumption in assumptions:
        print(f"- {assumption[0]}")
        print(f"  Invalid when: {assumption[1]}")

    assert assumptions, "No assumptions persisted."

    observation = (
        "Atlas is now receiving 47,000 requests per day, "
        "far above the traffic level originally expected."
    )

    print("\n3. New evidence arrives:")
    print(observation)

    print("\n4. Axiom retrieves related memory and evaluates assumptions...")

    evaluations = process_observation(
        str(project_id),
        observation,
    )

    assert evaluations, "No assumptions were evaluated."

    print("\n5. Evaluation results:")

    for evaluation in evaluations:
        print("\nAssumption:")
        print(evaluation["assumption"])

        print("Verdict:", evaluation["verdict"])
        print("Confidence:", evaluation["confidence"])
        print("Explanation:", evaluation["explanation"])

    updated_decision = get_decision(decision_id)

    print("\n6. Decision lifecycle:")
    print("Before: ACTIVE")
    print("After :", updated_decision[4])

    assert updated_decision[4] == "AT_RISK", (
        f"Expected AT_RISK, got {updated_decision[4]}"
    )

    print("\n========================================")
    print("✅ AXIOM END-TO-END TEST PASSED")
    print("Decision memory persisted.")
    print("New evidence was semantically connected.")
    print("Historical assumptions were evaluated.")
    print("Decision transitioned ACTIVE → AT_RISK.")
    print("========================================\n")


if __name__ == "__main__":
    main()
