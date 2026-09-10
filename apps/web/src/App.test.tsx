import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const API = "http://axiom.test";

const DECISION = {
  decisionId: "11111111-1111-1111-1111-111111111111",
  status: "ACTIVE",
  decision: {
    title: "Host Atlas on Render",
    statement: "Atlas is hosted on Render.",
    rationale: "Traffic and spend were expected to stay low.",
    confidence: 0.925,
    assumptions: [
      {
        statement: "Traffic stays below 10,000 requests per day.",
        invalidation_condition: "Traffic exceeds 10,000 requests per day.",
      },
      {
        statement: "Spend stays below $100 per month.",
        invalidation_condition: "Spend exceeds $100 per month.",
      },
    ],
  },
};

const EVALUATION = {
  decision_id: DECISION.decisionId,
  assumption: "Traffic stays below 10,000 requests per day.",
  verdict: "INVALIDATES",
  confidence: 0.996,
  explanation: "Observed traffic is 4.7x the assumed ceiling.",
};

function jsonResponse(body: unknown) {
  return { ok: true, json: async () => body };
}

type Routes = {
  project?: unknown;
  decision?: unknown;
  observation?: unknown;
};

/** Route fetch by URL so tests only declare the responses they care about. */
function mockFetch(routes: Routes) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/projects")) {
      return routes.project ?? jsonResponse({ id: "project-1" });
    }
    if (url.endsWith("/decisions")) {
      return routes.decision ?? jsonResponse(DECISION);
    }
    if (url.endsWith("/observations")) {
      return routes.observation ?? jsonResponse({ evaluations: [], atRisk: false });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function requestFor(fetchMock: ReturnType<typeof mockFetch>, suffix: string) {
  const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith(suffix));
  if (!call) throw new Error(`No request to ${suffix}`);
  const [url, init] = call as unknown as [string, RequestInit];
  return { url, init, body: JSON.parse(String(init.body)) };
}

const rememberButton = () => screen.getByRole("button", { name: "Remember Decision" });
const evaluateButton = () => screen.getByRole("button", { name: "Evaluate Evidence" });

async function rememberDecision(routes: Routes = {}) {
  const fetchMock = mockFetch(routes);
  render(<App />);
  fireEvent.click(rememberButton());
  return fetchMock;
}

let alertMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  alertMock = vi.fn();
  vi.stubGlobal("alert", alertMock);
});

describe("initial render", () => {
  it("shows the pitch and prefilled demo inputs", () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Decisions have consequences.Axiom remembers why."
    );
    expect(screen.getByText("Capture a decision")).toBeInTheDocument();
    expect(screen.getByText("Introduce new evidence")).toBeInTheDocument();

    const [decisionInput, observationInput] = screen.getAllByRole("textbox");
    expect(decisionInput).toHaveValue(
      "We decided to host Atlas on Render because we expect fewer than 10000 requests per day and want infrastructure spending below 100 dollars per month."
    );
    expect(observationInput).toHaveValue(
      "Atlas is now receiving 47000 requests per day, far above the traffic level originally expected."
    );
  });

  it("blocks evidence evaluation until a decision exists", () => {
    render(<App />);

    expect(evaluateButton()).toBeDisabled();
    expect(rememberButton()).toBeEnabled();
  });

  it("renders no memory or reasoning panels", () => {
    render(<App />);

    expect(screen.queryByText("COCKROACHDB MEMORY")).not.toBeInTheDocument();
    expect(screen.queryByText("BEDROCK REASONING")).not.toBeInTheDocument();
  });
});

describe("remembering a decision", () => {
  it("creates the project then posts the decision text", async () => {
    const fetchMock = await rememberDecision();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const project = requestFor(fetchMock, "/projects");
    expect(project.url).toBe(`${API}/projects`);
    expect(project.init.method).toBe("POST");
    expect(project.init.headers).toEqual({ "Content-Type": "application/json" });
    expect(project.body).toEqual({
      name: "Atlas Labs",
      description: "Production platform modernization",
    });

    const decision = requestFor(fetchMock, "/decisions");
    expect(decision.url).toBe(`${API}/projects/project-1/decisions`);
    expect(decision.body.text).toContain("host Atlas on Render");
  });

  it("posts the edited decision text", async () => {
    const fetchMock = mockFetch({});
    render(<App />);

    fireEvent.change(screen.getAllByRole("textbox")[0], {
      target: { value: "We decided to stay on bare metal." },
    });
    fireEvent.click(rememberButton());

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(requestFor(fetchMock, "/decisions").body).toEqual({
      text: "We decided to stay on bare metal.",
    });
  });

  it("renders the persisted decision with rounded confidence and assumptions", async () => {
    await rememberDecision();

    expect(await screen.findByText("Host Atlas on Render")).toBeInTheDocument();
    expect(
      screen.getByText("Traffic and spend were expected to stay low.")
    ).toBeInTheDocument();
    expect(screen.getByText(/Extraction confidence:\s*93%/)).toBeInTheDocument();

    for (const assumption of DECISION.decision.assumptions) {
      expect(screen.getByText(assumption.statement)).toBeInTheDocument();
      expect(
        screen.getByText(`Invalid when: ${assumption.invalidation_condition}`)
      ).toBeInTheDocument();
    }

    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(evaluateButton()).toBeEnabled();
  });

  it("shows progress messages and re-enables the buttons afterwards", async () => {
    const release: Record<string, (value: unknown) => void> = {};
    const pending = (key: string) =>
      new Promise((resolve) => {
        release[key] = resolve;
      });

    const pendingProject = pending("project");
    const pendingDecision = pending("decision");

    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/projects")) {
          await pendingProject;
          return jsonResponse({ id: "project-1" });
        }
        await pendingDecision;
        return jsonResponse(DECISION);
      })
    );

    render(<App />);
    fireEvent.click(rememberButton());

    expect(await screen.findByText("Creating project...")).toBeInTheDocument();
    expect(rememberButton()).toBeDisabled();

    release.project(undefined);

    expect(
      await screen.findByText("Axiom is extracting and remembering the decision...")
    ).toBeInTheDocument();
    expect(rememberButton()).toBeDisabled();

    release.decision(undefined);

    await waitFor(() => expect(rememberButton()).toBeEnabled());
    expect(screen.queryByText("Creating project...")).not.toBeInTheDocument();
  });

  it("alerts and renders nothing when project creation fails", async () => {
    await rememberDecision({ project: { ok: false, json: async () => ({}) } });

    await waitFor(() =>
      expect(alertMock).toHaveBeenCalledWith("Project creation failed.")
    );
    expect(screen.queryByText("COCKROACHDB MEMORY")).not.toBeInTheDocument();
    expect(evaluateButton()).toBeDisabled();
  });

  it("alerts when decision processing fails", async () => {
    await rememberDecision({ decision: { ok: false, json: async () => ({}) } });

    await waitFor(() =>
      expect(alertMock).toHaveBeenCalledWith("Decision processing failed.")
    );
    expect(screen.queryByText("COCKROACHDB MEMORY")).not.toBeInTheDocument();
  });

  it("falls back to a generic alert for non-error rejections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject("socket hang up"))
    );

    render(<App />);
    fireEvent.click(rememberButton());

    await waitFor(() => expect(alertMock).toHaveBeenCalledWith("Unexpected error."));
  });
});

describe("evaluating new evidence", () => {
  async function captureThenEvaluate(routes: Routes = {}) {
    const fetchMock = await rememberDecision(routes);
    await waitFor(() => expect(evaluateButton()).toBeEnabled());
    fireEvent.click(evaluateButton());
    return fetchMock;
  }

  it("posts the observation for the created project", async () => {
    const fetchMock = await captureThenEvaluate();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    const observation = requestFor(fetchMock, "/observations");
    expect(observation.url).toBe(`${API}/projects/project-1/observations`);
    expect(observation.init.method).toBe("POST");
    expect(observation.body.content).toContain("47000 requests per day");
  });

  it("posts the edited observation text", async () => {
    const fetchMock = await rememberDecision();
    await waitFor(() => expect(evaluateButton()).toBeEnabled());

    fireEvent.change(screen.getAllByRole("textbox")[1], {
      target: { value: "Spend is now $180 per month." },
    });
    fireEvent.click(evaluateButton());

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(requestFor(fetchMock, "/observations").body).toEqual({
      content: "Spend is now $180 per month.",
    });
  });

  it("renders each evaluation and flips the decision to AT RISK", async () => {
    await captureThenEvaluate({
      observation: jsonResponse({ evaluations: [EVALUATION], atRisk: true }),
    });

    expect(await screen.findByText("BEDROCK REASONING")).toBeInTheDocument();
    expect(screen.getByText("INVALIDATES")).toBeInTheDocument();
    expect(screen.getByText("100% confidence")).toBeInTheDocument();
    expect(screen.getByText(EVALUATION.explanation)).toBeInTheDocument();
    expect(screen.getByText("AT RISK")).toBeInTheDocument();
    expect(screen.queryByText("ACTIVE")).not.toBeInTheDocument();
  });

  it("keeps the decision ACTIVE when the evidence is not disqualifying", async () => {
    await captureThenEvaluate({
      observation: jsonResponse({
        evaluations: [{ ...EVALUATION, verdict: "WEAKENS", confidence: 0.6 }],
        atRisk: false,
      }),
    });

    expect(await screen.findByText("WEAKENS")).toBeInTheDocument();
    expect(screen.getByText("60% confidence")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
  });

  it("hides the reasoning panel when no assumption is affected", async () => {
    await captureThenEvaluate({
      observation: jsonResponse({ evaluations: [], atRisk: false }),
    });

    await waitFor(() =>
      expect(screen.queryByText("Searching memory and evaluating assumptions...")).not
        .toBeInTheDocument()
    );
    expect(screen.queryByText("BEDROCK REASONING")).not.toBeInTheDocument();
  });

  it("alerts when evidence evaluation fails", async () => {
    await captureThenEvaluate({
      observation: { ok: false, json: async () => ({}) },
    });

    await waitFor(() =>
      expect(alertMock).toHaveBeenCalledWith("Evidence evaluation failed.")
    );
    expect(screen.queryByText("BEDROCK REASONING")).not.toBeInTheDocument();
  });

  it("falls back to a generic alert for non-error rejections", async () => {
    const fetchMock = await rememberDecision();
    await waitFor(() => expect(evaluateButton()).toBeEnabled());

    fetchMock.mockImplementation(() => Promise.reject("socket hang up"));
    fireEvent.click(evaluateButton());

    await waitFor(() => expect(alertMock).toHaveBeenCalledWith("Unexpected error."));
  });

  it("clears previous evaluations when a new decision is remembered", async () => {
    await captureThenEvaluate({
      observation: jsonResponse({ evaluations: [EVALUATION], atRisk: true }),
    });

    expect(await screen.findByText("AT RISK")).toBeInTheDocument();

    fireEvent.click(rememberButton());

    await waitFor(() =>
      expect(screen.queryByText("BEDROCK REASONING")).not.toBeInTheDocument()
    );
    expect(await screen.findByText("ACTIVE")).toBeInTheDocument();
  });
});
