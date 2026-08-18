# Axiom

**Decisions have consequences. Axiom remembers why.**

Axiom is an agentic decision-intelligence platform that captures why technical decisions were made, preserves their assumptions as persistent memory, and re-evaluates those assumptions when new evidence appears.

## What Axiom solves

Teams often remember **what** they decided but lose:

- why they made the decision
- assumptions behind it
- constraints at the time
- evidence supporting it
- conditions that would make it invalid

Axiom turns static decisions into **living organizational memory**.

## How it works

1. A user submits a decision in natural language.
2. Amazon Bedrock extracts the decision, rationale, assumptions, and invalidation conditions.
3. The structured decision is stored in CockroachDB.
4. Amazon Titan Text Embeddings V2 generates a 1024-dimensional embedding.
5. CockroachDB Distributed Vector Indexing stores and retrieves semantically related memories.
6. When new evidence arrives, Axiom retrieves relevant historical decisions.
7. Amazon Bedrock evaluates each assumption against the new evidence.
8. Deterministic application logic changes the decision from `ACTIVE` to `AT_RISK` when an assumption is invalidated.

## Demo scenario

A team decides:

> Host Atlas on Render because traffic is expected to remain below 10,000 requests per day and infrastructure spend below $100/month.

Later, Axiom receives:

> Atlas is now receiving 47,000 requests per day.

Axiom retrieves the original decision and determines:

- Traffic assumption: `INVALIDATES`
- Confidence: `100%`
- Pricing assumption: `WEAKENS`
- Confidence: `85%`
- Decision state: `ACTIVE → AT_RISK`

## Architecture

```text
AWS Amplify Hosting
        |
        v
React + TypeScript
        |
        v
AWS Lambda Function URL
        |
        v
FastAPI / Axiom Agent
      /          \
     v            v
Amazon Bedrock   CockroachDB Cloud
Nova 2 Lite      Transactional memory
Titan Embed V2   VECTOR(1024)
                 Distributed Vector Index
                 Decision state
                 Evaluation history
                 Managed MCP Server
