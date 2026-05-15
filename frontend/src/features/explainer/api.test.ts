import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../shared/api/errors";
import { mockExplanationResponse } from "../../test/mockResponse";
import { explainPost, explainPostStream, getConfigStatus } from "./api";
import type { LiveProgressEvent } from "./types";

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

  it("reads streamed progress and result events split across chunks", async () => {
    const progressEvent: LiveProgressEvent = {
      type: "run_started",
      run_id: "run_test",
      status: "active",
      node_name: null,
      step: "Fetching post",
      message: "Live analysis started.",
      timestamp: "2026-05-15T00:00:00+00:00"
    };
    const stream = [
      `event: progress\ndata: ${JSON.stringify(progressEvent)}\n`,
      `\nevent: result\ndata: ${JSON.stringify(mockExplanationResponse)}\n\n`
    ];
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(stream));
    vi.stubGlobal("fetch", fetchMock);
    const progressEvents: LiveProgressEvent[] = [];

    const response = await explainPostStream(
      { url: "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v" },
      {
        onProgress: (event) => progressEvents.push(event)
      }
    );

    expect(progressEvents).toEqual([progressEvent]);
    expect(response.confidence).toBe("high");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/explain/stream",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("raises streamed backend errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse([
          'event: error\ndata: {"error":"search_provider_required","message":"Live search is not configured.","status":400}\n\n'
        ])
      )
    );

    await expect(
      explainPostStream(
        { url: "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v" },
        { onProgress: vi.fn() }
      )
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

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      }
    }),
    {
      status: 200,
      headers: { "Content-Type": "text/event-stream" }
    }
  );
}
