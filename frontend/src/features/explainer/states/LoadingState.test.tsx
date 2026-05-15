import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { LiveProgressState } from "../types";
import { LoadingState } from "./LoadingState";

describe("LoadingState", () => {
  it("renders completed, active, and pending pipeline states", () => {
    render(<LoadingState progress={progressState("Reading sources")} />);

    expect(screen.getByText("Fetching post").closest(".pipeline-step")).toHaveClass("completed");
    expect(screen.getByText("Reading sources").closest(".pipeline-step")).toHaveClass("active");
    expect(screen.getByText("Generating explanation").closest(".pipeline-step")).toHaveClass("pending");
  });

  it("renders a failed pipeline state", () => {
    const progress = progressState(null);
    render(
      <LoadingState
        progress={{
          ...progress,
          failedStep: "Searching context",
        }}
      />,
    );

    expect(screen.getByText("Searching context").closest(".pipeline-step")).toHaveClass("failed");
  });
});

function progressState(activeStep: LiveProgressState["activeStep"]): LiveProgressState {
  return {
    events: [
      {
        type: "node_started",
        run_id: "run_test",
        status: "active",
        node_name: "fetch_source_pages",
        step: "Reading sources",
        message: "Reading sources started.",
        timestamp: new Date().toISOString(),
      },
    ],
    activeStep,
    completedSteps: ["Fetching post", "Analyzing media", "Searching context"],
    failedStep: null,
  };
}
