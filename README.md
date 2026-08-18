# Axiom

**Decisions have consequences. Axiom remembers why.**

Axiom is an agentic decision-intelligence platform that captures why technical decisions were made, preserves the assumptions behind them as persistent memory, and re-evaluates those assumptions when new evidence appears.

## The Problem

Organizations make important technical decisions every day: architecture choices, infrastructure selections, vendor decisions, scaling strategies, and operational trade-offs.

The decision itself is usually recorded. The reasoning behind it often disappears.

Teams lose:

- why a decision was made
- assumptions that made it reasonable
- constraints that existed at the time
- evidence supporting it
- conditions that would invalidate it

Axiom turns these static decisions into **living organizational memory**.

## What Axiom Does

Axiom follows a continuous decision-memory lifecycle:

```text
Decision
   |
   v
Extract rationale + assumptions
   |
   v
Persist structured memory
   |
   v
Generate semantic embedding
   |
   v
New evidence arrives
   |
   v
Retrieve relevant historical memory
   |
   v
Re-evaluate assumptions
   |
   v
Update decision risk
```

Instead of merely remembering previous conversations, Axiom remembers **why a decision was valid** and determines whether that reasoning still holds.

## Demo Scenario

A team makes this decision:

> Host Atlas on Render because traffic is expected to remain below 10,000 requests per day and infrastructure spending should remain below $100 per month.

Axiom extracts and persists the rationale and assumptions.

Later, new evidence arrives:

> Atlas is now receiving 47,000 requests per day.

Axiom retrieves the relevant historical memory and evaluates the evidence against the original assumptions.

Result:

```text
Traffic assumption
Verdict: INVALIDATES
Confidence: 100%

Pricing assumption
Verdict: WEAKENS
Confidence: 85%

Decision:
ACTIVE --> AT_RISK
```

The original decision has not simply been recalled.

**Its validity has been autonomously reconsidered using new evidence.**

## Architecture

```text
User
 |
 v
AWS Amplify Hosting
 |
 v
React + TypeScript + Vite
 |
 v
AWS Lambda Function URL
 |
 v
FastAPI + Mangum
 |
 +------------------------+
 |                        |
 v                        v
Amazon Bedrock       CockroachDB Cloud
 |                        |
 | Nova 2 Lite             +-- decisions
 | Titan Embed V2          +-- assumptions
 |                         +-- observations
 |                         +-- evaluations
 |                         +-- memory_objects
 |                         +-- VECTOR(1024)
 |                         +-- Distributed Vector Index
 |                         +-- Managed MCP Server
 +------------------------+
```

See [docs/architecture.md](docs/architecture.md) for the detailed architecture.

## Agentic Memory

Axiom treats memory as operational state rather than passive conversational history.

It persists:

- **Decision memory** — what was decided
- **Rationale memory** — why it was decided
- **Assumption memory** — what must remain true
- **Observation memory** — new evidence
- **Evaluation memory** — how evidence affects assumptions
- **Semantic memory** — vector representations used for retrieval

This enables a feedback loop where historical reasoning directly influences future agent behavior.

## CockroachDB

CockroachDB is Axiom's persistent memory and transactional system of record.

### Distributed Vector Indexing

Amazon Titan Text Embeddings V2 generates **1024-dimensional embeddings**.

Axiom stores these using:

```sql
VECTOR(1024)
```

CockroachDB's distributed vector capabilities allow Axiom to retrieve historical memories semantically related to new evidence.

The workflow is:

```text
Observation
    |
    v
Titan Embedding
    |
    v
CockroachDB Vector Search
    |
    v
Relevant Historical Memory
    |
    v
Assumption Evaluation
```

Vector retrieval determines what historical context should be reconsidered, while relational records remain the authoritative state.

### CockroachDB Managed MCP

Axiom also integrates with the **CockroachDB Cloud Managed MCP Server**.

The MCP integration uses:

- OAuth authentication
- read-only data access
- Codex as an MCP client
- the live CockroachDB cluster used by Axiom

The MCP server independently inspected Axiom's persisted memory and confirmed:

```text
Decision: Hosting Atlas on Render
Status: AT_RISK

Traffic assumption:
INVALIDATES — 100%

Pricing assumption:
WEAKENS — 85%
```

MCP access is intentionally read-only. Runtime writes remain controlled by the Axiom application.

## Amazon Bedrock

Axiom uses Amazon Bedrock for both reasoning and semantic memory.

### Amazon Nova 2 Lite

Used for:

- decision extraction
- rationale extraction
- assumption generation
- invalidation-condition generation
- evidence evaluation

### Amazon Titan Text Embeddings V2

Used to generate the 1024-dimensional vectors stored in CockroachDB.

This creates a separation between:

```text
Reasoning     -> Amazon Nova 2 Lite
Semantic memory -> Amazon Titan Text Embeddings V2
Persistent state -> CockroachDB
```

## AWS Deployment

The production MVP is deployed serverlessly on AWS.

### AWS Amplify Hosting

Hosts the React/Vite frontend.

### AWS Lambda

Runs the FastAPI backend using Mangum.

The serverless architecture minimizes infrastructure management and keeps the MVP inexpensive to operate.

### AWS IAM

The Lambda execution role authorizes Bedrock access without storing AWS access keys in application code.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Hosting | AWS Amplify |
| API | FastAPI |
| Compute | AWS Lambda |
| Lambda adapter | Mangum |
| Reasoning | Amazon Nova 2 Lite |
| Embeddings | Amazon Titan Text Embeddings V2 |
| Database | CockroachDB Cloud |
| Vector memory | CockroachDB VECTOR(1024) |
| MCP | CockroachDB Cloud Managed MCP |
| Authentication to MCP | OAuth |

## Repository Structure

```text
Axiom/
├── apps/
│   ├── api/
│   │   ├── requirements.txt
│   │   └── src/
│   └── web/
│       └── React/Vite application
│
├── database/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   └── 002_vector_memory.sql
│   └── README.md
│
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── api.md
│   ├── demo-scenario.md
│   ├── memory-model.md
│   └── security.md
│
├── scripts/
│   ├── test_axiom_flow.py
│   ├── test_reasoning.py
│   └── test_vector_memory.py
│
├── .env.example
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

## Local Development

### 1. Clone

```bash
git clone https://github.com/GibzB/Axiom.git
cd Axiom
```

### 2. Configure Python

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r apps/api/requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Configure the required values:

```text
DATABASE_URL
BEDROCK_GENERATION_MODEL_ID
BEDROCK_EMBEDDING_MODEL_ID
BEDROCK_EMBEDDING_DIMENSIONS
```

### 4. Run the API

```bash
set -a
source .env
set +a

PYTHONPATH=apps/api python -m uvicorn src.main:app \
  --host 127.0.0.1 \
  --port 8000
```

Test:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{
  "status": "ok",
  "service": "axiom-api"
}
```

### 5. Run the Frontend

```bash
cd apps/web

npm install
npm run dev
```

## Testing

### Vector Memory

```bash
python scripts/test_vector_memory.py
```

Validates:

```text
Bedrock embedding
→ VECTOR(1024)
→ CockroachDB
→ semantic retrieval
```

### Reasoning

```bash
python scripts/test_reasoning.py
```

Validates structured decision extraction and assumption evaluation.

### End-to-End Agentic Memory

```bash
python scripts/test_axiom_flow.py
```

Validates:

```text
Decision capture
      ↓
Persistent assumptions
      ↓
Semantic memory
      ↓
New evidence
      ↓
Relevant-memory retrieval
      ↓
Assumption evaluation
      ↓
ACTIVE → AT_RISK
```

## Security

The MVP uses:

- TLS-encrypted CockroachDB connections
- AWS IAM-based Bedrock authorization
- OAuth-authenticated Managed MCP
- read-only MCP permissions
- environment-based secrets
- `.gitignore` protection for local credentials
- application-controlled authoritative state transitions

See [docs/security.md](docs/security.md).

## Why Axiom Is Different

Most AI memory systems answer:

> **What happened before?**

Axiom asks:

> **Why did we make this decision, what assumptions made it valid, and are those assumptions still true?**

That distinction turns memory from passive context into an active reasoning mechanism.

Axiom does not remember merely to produce a better response.

**Axiom remembers so it knows when the world has changed enough to act.**

## License

Axiom is released under the MIT License.
