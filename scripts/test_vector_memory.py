import os
import sys
import uuid

import psycopg

sys.path.insert(0, "apps/api")

from src.services.embeddings import generate_embedding


DATABASE_URL = os.environ["DATABASE_URL"]


def vector_literal(values):
    return "[" + ",".join(str(float(v)) for v in values) + "]"


decision_text = (
    "Atlas will use Render because expected traffic will remain "
    "below 10,000 requests per day."
)

query_text = (
    "Traffic has increased to 47,000 requests per day and "
    "the current hosting platform is experiencing capacity problems."
)

print("Generating decision embedding...")
decision_embedding = generate_embedding(decision_text)

print("Generating query embedding...")
query_embedding = generate_embedding(query_text)

project_id = uuid.uuid4()
entity_id = uuid.uuid4()

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
                "Axiom semantic-memory test project",
            ),
        )

        cur.execute(
            """
            INSERT INTO axiom.public.memory_objects
                (
                    project_id,
                    entity_type,
                    entity_id,
                    memory_type,
                    content,
                    embedding
                )
            VALUES (%s, %s, %s, %s, %s, %s::VECTOR)
            """,
            (
                project_id,
                "DECISION",
                entity_id,
                "DECISION_MEMORY",
                decision_text,
                vector_literal(decision_embedding),
            ),
        )

        cur.execute(
            """
            SELECT
                content,
                embedding <=> %s::VECTOR AS cosine_distance
            FROM axiom.public.memory_objects
            WHERE project_id = %s
              AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::VECTOR
            LIMIT 5
            """,
            (
                vector_literal(query_embedding),
                project_id,
                vector_literal(query_embedding),
            ),
        )

        results = cur.fetchall()

print("\n=== AXIOM MEMORY RETRIEVAL ===")

for content, distance in results:
    similarity = 1 - float(distance)

    print(f"Memory: {content}")
    print(f"Similarity: {similarity:.4f}")

    if similarity > 0.30:
        print("✅ Semantically related memory retrieved")
    else:
        print("⚠️ Weak semantic relationship")

assert results, "No memory retrieved."

print("\n✅ AXIOM VECTOR MEMORY TEST PASSED")
