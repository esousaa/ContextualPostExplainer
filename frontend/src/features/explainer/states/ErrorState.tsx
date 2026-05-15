import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "../../../shared/components/Button";
import type { ApiError } from "../types";

type ErrorStateProps = {
  error: ApiError;
  onRetry: () => void;
};

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <section className="state-panel error-state" role="alert">
      <AlertTriangle size={26} />
      <h2>{titleForError(error.error)}</h2>
      <p>{error.message}</p>
      <BadgeCode code={error.error} />
      <Button icon={<RefreshCw size={16} />} onClick={onRetry} variant="secondary">
        Retry
      </Button>
    </section>
  );
}

function titleForError(error: string) {
  if (error === "search_provider_required") return "Live search is not configured";
  if (error === "unsupported_platform") return "Unsupported platform";
  if (error === "post_not_found") return "Post not found";
  if (error === "network_error") return "Backend unavailable";
  if (error === "timeout") return "Request timed out";
  return "Request failed";
}

function BadgeCode({ code }: { code: string }) {
  return <span className="error-code">{code}</span>;
}
