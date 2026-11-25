import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import QAVerdictPanel from "./QAVerdictPanel";

describe("QAVerdictPanel decided_by support", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  test("renders deterministic_rules_v1 badge and allows human override with override_reason", async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          exists: true,
          verdict: "approve",
          reasoning: "Deterministic approve",
          ai_reasoning: "Deterministic approve",
          comment: "",
          override_reason: "",
          decided_by: "deterministic_rules_v1",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

    (global as any).fetch = mockFetch;

    render(<QAVerdictPanel jobId={101} clientName="TestClient" lang="EN" />);

    expect(
      await screen.findByText("Deterministic Rules Engine v1 — automatic decision")
    ).toBeInTheDocument();
    expect(screen.getByText(/Decision rationale/i)).toBeInTheDocument();
    expect(screen.queryByText(/AI Analysis/i)).toBeNull();
    expect(screen.queryByText(/Override AI Decision/i)).toBeNull();

    fireEvent.click(screen.getByText("Override decision"));
    expect(screen.queryByText(/AI Analysis/i)).toBeNull();
    expect(screen.queryByText(/Overriding AI verdict/i)).toBeNull();
    fireEvent.change(
      screen.getByPlaceholderText(/logo change not detected/i),
      { target: { value: "Manual check override" } }
    );
    fireEvent.click(screen.getByText(/Save as Human Override/i));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    const postCall = mockFetch.mock.calls[1];
    expect(postCall[0]).toBe("/api/v1/compare/101/decision");
    const body = JSON.parse(postCall[1].body);
    expect(body.decided_by).toBe("human");
    expect(body.override_reason).toBe("Manual check override");

    expect(
      await screen.findByText("Human override — decision changed by QA user")
    ).toBeInTheDocument();
  });

  test("renders AI Analyst badge for decided_by=agent", async () => {
    (global as any).fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        exists: true,
        verdict: "review",
        reasoning: "AI review",
        ai_reasoning: "AI review",
        decided_by: "agent",
      }),
    });

    render(<QAVerdictPanel jobId={102} clientName="TestClient" lang="EN" />);

    expect(
      await screen.findByText("AI Analyst (Agent 2) — automatic decision")
    ).toBeInTheDocument();
  });
});
