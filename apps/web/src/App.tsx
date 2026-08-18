import { useState } from "react";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Database,
  Loader2,
} from "lucide-react";
import "./App.css";

const API = import.meta.env.VITE_API_URL;

type DecisionResponse = {
  decisionId: string;
  status: string;
  decision: {
    title: string;
    statement: string;
    rationale: string;
    confidence: number;
    assumptions: {
      statement: string;
      invalidation_condition: string;
    }[];
  };
};

type Evaluation = {
  decision_id: string;
  assumption: string;
  verdict: string;
  confidence: number;
  explanation: string;
};

export default function App() {
  const [projectId, setProjectId] = useState("");
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [atRisk, setAtRisk] = useState(false);
  const [loading, setLoading] = useState("");

  const [decisionText, setDecisionText] = useState(
    "We decided to host Atlas on Render because we expect fewer than 10000 requests per day and want infrastructure spending below 100 dollars per month."
  );

  const [observation, setObservation] = useState(
    "Atlas is now receiving 47000 requests per day, far above the traffic level originally expected."
  );

  async function rememberDecision() {
    try {
      setLoading("Creating project...");
      setEvaluations([]);
      setAtRisk(false);

      const projectRes = await fetch(`${API}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Atlas Labs",
          description: "Production platform modernization",
        }),
      });

      if (!projectRes.ok) throw new Error("Project creation failed.");

      const project = await projectRes.json();
      setProjectId(project.id);

      setLoading("Axiom is extracting and remembering the decision...");

      const decisionRes = await fetch(
        `${API}/projects/${project.id}/decisions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: decisionText }),
        }
      );

      if (!decisionRes.ok) throw new Error("Decision processing failed.");

      const data = await decisionRes.json();
      setDecision(data);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Unexpected error.");
    } finally {
      setLoading("");
    }
  }

  async function evaluateEvidence() {
    if (!projectId) return;

    try {
      setLoading("Searching memory and evaluating assumptions...");

      const response = await fetch(
        `${API}/projects/${projectId}/observations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: observation }),
        }
      );

      if (!response.ok) throw new Error("Evidence evaluation failed.");

      const data = await response.json();

      setEvaluations(data.evaluations);
      setAtRisk(data.atRisk);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Unexpected error.");
    } finally {
      setLoading("");
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Brain size={28} />
          <span>AXIOM</span>
        </div>

        <span className="tag">Persistent Decision Intelligence</span>
      </header>

      <section className="hero">
        <p className="eyebrow">AGENTIC MEMORY FOR REAL DECISIONS</p>

        <h1>
          Decisions have consequences.
          <br />
          Axiom remembers why.
        </h1>

        <p className="hero-copy">
          Axiom captures decisions, preserves their assumptions, and uses
          persistent memory to detect when new evidence makes old reasoning
          unsafe.
        </p>
      </section>

      <section className="workflow-grid">
        <article className="card">
          <div className="step">01</div>
          <h2>Capture a decision</h2>

          <textarea
            value={decisionText}
            onChange={(e) => setDecisionText(e.target.value)}
          />

          <button onClick={rememberDecision} disabled={!!loading}>
            Remember Decision
          </button>
        </article>

        <article className="card">
          <div className="step">02</div>
          <h2>Introduce new evidence</h2>

          <textarea
            value={observation}
            onChange={(e) => setObservation(e.target.value)}
          />

          <button
            onClick={evaluateEvidence}
            disabled={!decision || !!loading}
          >
            Evaluate Evidence
          </button>
        </article>
      </section>

      {loading && (
        <div className="processing">
          <Loader2 className="spin" size={20} />
          {loading}
        </div>
      )}

      {decision && (
        <section className="card memory-card">
          <div className="status-header">
            <div>
              <p className="section-label">COCKROACHDB MEMORY</p>
              <h2 className="memory-title">
                <Database size={22} />
                Persistent Decision
              </h2>
            </div>

            <span className={atRisk ? "badge danger" : "badge active"}>
              {atRisk ? (
                <AlertTriangle size={16} />
              ) : (
                <CheckCircle2 size={16} />
              )}
              {atRisk ? "AT RISK" : "ACTIVE"}
            </span>
          </div>

          <h3>{decision.decision.title}</h3>
          <p>{decision.decision.rationale}</p>

          <div className="confidence">
            Extraction confidence:{" "}
            {Math.round(decision.decision.confidence * 100)}%
          </div>

          <h4>Remembered assumptions</h4>

          <div className="assumption-list">
            {decision.decision.assumptions.map((assumption, index) => (
              <div className="assumption" key={index}>
                <strong>{assumption.statement}</strong>
                <span>
                  Invalid when: {assumption.invalidation_condition}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {evaluations.length > 0 && (
        <section className="card">
          <p className="section-label">BEDROCK REASONING</p>
          <h2>Agent evaluation</h2>

          <div className="evaluation-list">
            {evaluations.map((evaluation, index) => (
              <div className="evaluation" key={index}>
                <div className="evaluation-header">
                  <strong>{evaluation.verdict}</strong>
                  <span>
                    {Math.round(evaluation.confidence * 100)}% confidence
                  </span>
                </div>

                <p className="evaluation-assumption">
                  {evaluation.assumption}
                </p>

                <p>{evaluation.explanation}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
