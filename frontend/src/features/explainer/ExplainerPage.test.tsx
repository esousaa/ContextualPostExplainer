import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockExplanationResponse } from "../../test/mockResponse";
import { ExplainerPage } from "./ExplainerPage";

describe("ExplainerPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("runs the explain flow and renders cited bullets, labels, and source roles", async () => {
    vi.stubGlobal("fetch", vi.fn(mockFetchSuccess));
    const user = userEvent.setup();

    render(<ExplainerPage />);
    await user.click(screen.getByRole("button", { name: /explain/i }));

    expect(await screen.findByText(/The DOJ filed a lawsuit/i)).toBeInTheDocument();
    expect(screen.getByText("confirmed fact")).toBeInTheDocument();
    expect(screen.getByText("news outlet")).toBeInTheDocument();
    expect(screen.getByText("independent context")).toBeInTheDocument();
    expect(screen.getAllByText("OFFICIAL_POSITION_VIA_NEWS".toLowerCase().replaceAll("_", " "))[0]).toBeInTheDocument();
  });

  it("renders a specific configuration error from the backend", async () => {
    vi.stubGlobal("fetch", vi.fn(mockFetchConfigError));
    const user = userEvent.setup();

    render(<ExplainerPage />);
    await user.click(screen.getByRole("button", { name: /explain/i }));

    expect(await screen.findByText("Live search is not configured")).toBeInTheDocument();
    expect(screen.getByText("search_provider_required")).toBeInTheDocument();
  });
});

function mockFetchSuccess(input: RequestInfo | URL) {
  const url = String(input);
  if (url.endsWith("/api/config/status")) {
    return Promise.resolve(
      new Response(
        JSON.stringify({
          status: "ok",
          live_search: {
            provider: "tavily",
            configured: true
          }
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
  }

  return Promise.resolve(
    new Response(JSON.stringify(mockExplanationResponse), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    })
  );
}

function mockFetchConfigError(input: RequestInfo | URL) {
  const url = String(input);
  if (url.endsWith("/api/config/status")) {
    return Promise.resolve(
      new Response(
        JSON.stringify({
          status: "ok",
          live_search: {
            provider: null,
            configured: false
          }
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
  }

  return Promise.resolve(
    new Response(
      JSON.stringify({
        error: "search_provider_required",
        message: "Live mode requires SEARCH_PROVIDER and the matching provider API key."
      }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    )
  );
}
