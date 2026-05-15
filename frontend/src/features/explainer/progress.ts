import type { LiveProgressEvent, LiveProgressState, PipelineStepName, PipelineStepStatus } from "./types";

export const PIPELINE_STEPS: PipelineStepName[] = [
  "Fetching post",
  "Analyzing media",
  "Searching context",
  "Reading sources",
  "Ranking evidence",
  "Generating explanation",
];

export function createInitialProgress(): LiveProgressState {
  return {
    events: [],
    activeStep: null,
    completedSteps: [],
    failedStep: null,
  };
}

export function applyProgressEvent(
  progress: LiveProgressState,
  event: LiveProgressEvent,
): LiveProgressState {
  const completed = new Set(progress.completedSteps);
  const stepIndex = PIPELINE_STEPS.indexOf(event.step);

  if (stepIndex > 0) {
    for (const previousStep of PIPELINE_STEPS.slice(0, stepIndex)) {
      completed.add(previousStep);
    }
  }

  if (event.status === "completed") {
    completed.add(event.step);
  }

  return {
    events: [...progress.events, event],
    activeStep: event.status === "completed" ? null : event.step,
    completedSteps: PIPELINE_STEPS.filter((step) => completed.has(step)),
    failedStep: null,
  };
}

export function failProgress(progress: LiveProgressState): LiveProgressState {
  return {
    ...progress,
    activeStep: null,
    failedStep: progress.activeStep,
  };
}

export function getPipelineStepStatus(
  progress: LiveProgressState,
  step: PipelineStepName,
): PipelineStepStatus {
  if (progress.failedStep === step) {
    return "failed";
  }

  if (progress.completedSteps.includes(step)) {
    return "completed";
  }

  if (progress.activeStep === step) {
    return "active";
  }

  return "pending";
}

export function activeStepStartedAt(progress: LiveProgressState): string | null {
  if (!progress.activeStep) {
    return null;
  }

  const matchingEvents = progress.events.filter(
    (event) =>
      event.step === progress.activeStep &&
      (event.type === "run_started" || event.type === "node_started"),
  );
  return matchingEvents.at(-1)?.timestamp ?? null;
}
