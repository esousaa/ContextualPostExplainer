import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../shared/api/errors";
import { mockExplanationResponse } from "../../test/mockResponse";
import { explainPost, getConfigStatus } from "./api";

describe("explainer api", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends explain requests to the backend contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockExplanationResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await explainPost({
      url: "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v"
    });

    expect(response.explanation[0].claim_label).toBe("confirmed_fact");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/explain",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          url: "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v",
          include_debug: false
        })
      })
    );
  });

  it("preserves backend errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: "search_provider_required",
            message: "Live mode requires SEARCH_PROVIDER and the matching provider API key."
          }),
          {
            status: 400,
            headers: { "Content-Type": "application/json" }
          }
        )
      )
    );

    await expect(
      explainPost({
        url: "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v"
      })
    ).rejects.toMatchObject({
      error: "search_provider_required",
      status: 400
    } satisfies Partial<ApiClientError>);
  });

  it("loads config status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: "ok",
            live_search: {
              provider: "tavily",
              configured: true
            }
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" }
          }
        )
      )
    );

    await expect(getConfigStatus()).resolves.toMatchObject({
      live_search: {
        provider: "tavily",
        configured: true
      }
    });
  });
});
