# Axiom Architecture

## Overview

Axiom is a serverless agentic decision-intelligence system deployed on AWS with CockroachDB Cloud as its persistent memory layer.

```text
User
 |
 v
AWS Amplify Hosting
 |
 v
React / TypeScript / Vite
 |
 v
AWS Lambda Function URL
 |
 v
FastAPI + Mangum
 |
 +-----------------------+
 |                       |
 v                       v
Amazon Bedrock       CockroachDB Cloud
 |                       |
 | Nova 2 Lite            +-- projects
 | Titan Embed V2         +-- decisions
 |                        +-- assumptions
 |                        +-- observations
 |                        +-- evaluations
 |                        +-- memory_objects
 |                        +-- VECTOR(1024)
 |                        +-- Distributed Vector Index
 |                        +-- Managed MCP Server
 +-----------------------+
```

## Decision Capture Flow

1. The user submits a technical decision.
2. FastAPI receives the request through AWS Lambda.
3. Amazon Nova 2 Lite extracts the decision, rationale, assumptions, and invalidation conditions.
4. Axiom persists the structured decision in CockroachDB.
5. Amazon Titan Text Embeddings V2 creates a 1024-dimensional embedding.
6. The embedding is stored alongside transactional memory.

## Evidence Evaluation Flow

```text
New Observation
      |
      v
Titan Embedding
      |
      v
CockroachDB Vector Search
      |
      v
Relevant Persistent Memory
      |
      v
Nova 2 Lite Evaluation
      |
      v
Assumption Verdict
      |
      v
Deterministic State Transition
      |
      v
ACTIVE --> AT_RISK
```

Axiom demonstrated evidence verdicts including `INVALIDATES` and `WEAKENS`.

The model performs reasoning while application logic controls authoritative decision-state changes.

## Persistent Memory Model

CockroachDB is Axiom's system of record.

Axiom persists:

- decisions and rationale
- assumptions and invalidation conditions
- observations
- assumption evaluations
- agent runs
- semantic memory objects
- 1024-dimensional embeddings

Relational state and semantic memory therefore live in the same distributed database.

## Distributed Vector Indexing

Axiom stores Amazon Titan Text Embeddings V2 embeddings using CockroachDB's `VECTOR(1024)` data type.

When new evidence arrives, vector similarity identifies relevant historical memory before Amazon Bedrock evaluates the evidence against the stored assumptions.

This makes memory operational: previous reasoning influences future agent action.

## Managed MCP Server

CockroachDB Cloud Managed MCP provides an independent interface to Axiom's persisted memory.

The integration uses:

- CockroachDB Cloud Managed MCP
- OAuth authentication
- read-only data permissions
- Codex as the MCP client

MCP independently inspected the Atlas decision and confirmed:

- decision status: `AT_RISK`
- traffic assumption: `INVALIDATES`
- evaluation confidence: `100%`
- pricing assumption: `WEAKENS`
- evaluation confidence: `85%`

MCP is intentionally read-only. Application writes remain controlled by the Axiom backend.

## AWS Architecture

### AWS Amplify Hosting

Hosts the production React/Vite frontend.

### AWS Lambda

Runs the FastAPI backend through Mangum using serverless execution.

### Amazon Bedrock

Axiom uses:

- **Amazon Nova 2 Lite** for structured reasoning and assumption evaluation.
- **Amazon Titan Text Embeddings V2** for 1024-dimensional semantic memory embeddings.

### AWS IAM

The Lambda execution role authorizes Bedrock access without embedding AWS credentials in application code.

## Security Boundaries

Axiom uses:

- TLS for CockroachDB connections
- IAM-based AWS authorization
- OAuth for Managed MCP
- read-only MCP permissions
- environment-based database credentials
- `.gitignore` protection for secrets
- application-controlled decision-state transitions

## Demonstrated End-to-End Scenario

```text
"Host Atlas on Render"
        |
        v
Decision + assumptions persisted
        |
        v
Expected traffic < 10,000/day
        |
        v
New observation: 47,000/day
        |
        v
Semantic memory retrieval
        |
        v
Traffic assumption INVALIDATES (100%)
Pricing assumption WEAKENS (85%)
        |
        v
Decision: ACTIVE --> AT_RISK
```

The important architectural property is that memory is not passive context.

**Persisted memory changes what the agent does when new evidence arrives.**
