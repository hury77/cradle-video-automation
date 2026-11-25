import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import SystemEngineBadge from "./SystemEngineBadge";

describe("SystemEngineBadge", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  test("renders read-only decision engine badge in PL from /api/v1/system/info", async () => {
    (global as any).fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        decision_engine: "deterministic_rules_v1",
        advisor_provider: "none",
        engine_version: "1.0.0",
        git_sha: "2af4f4f",
      }),
    });

    render(<SystemEngineBadge lang="PL" />);
    const badge = await screen.findByTestId("system-engine-badge");
    expect(badge).toHaveTextContent("Silnik decyzji: deterministic_rules_v1");
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  test("renders read-only decision engine badge in EN", async () => {
    (global as any).fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ decision_engine: "deterministic_rules_v1" }),
    });

    render(<SystemEngineBadge lang="EN" />);
    const badge = await screen.findByTestId("system-engine-badge");
    expect(badge).toHaveTextContent("Decision engine: deterministic_rules_v1");
  });

  test("hides badge gracefully when /api/v1/system/info fails or times out", async () => {
    (global as any).fetch = jest.fn().mockRejectedValueOnce(new Error("Network timeout"));

    render(<SystemEngineBadge lang="EN" />);
    await waitFor(() => expect((global as any).fetch).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("system-engine-badge")).toBeNull();
  });
});
