import { useCallback, useEffect, useMemo, useState } from "react";

import { AnalysisPage } from "../features/analysis/AnalysisPage";
import { ExplainerPage } from "../features/explainer/ExplainerPage";
import { ObservabilityPage } from "../features/observability/ObservabilityPage";

export function App() {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    function handlePopState() {
      setPath(window.location.pathname);
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = useCallback((nextPath: string) => {
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setPath(nextPath);
  }, []);

  const route = useMemo(() => parseRoute(path), [path]);

  if (route.name === "observability") {
    return <ObservabilityPage onNavigate={navigate} selectedRunId={route.runId} />;
  }
  if (route.name === "analysis") {
    return <AnalysisPage onNavigate={navigate} />;
  }

  return <ExplainerPage onNavigate={navigate} />;
}

function parseRoute(
  path: string,
): { name: "explain" } | { name: "analysis" } | { name: "observability"; runId: string | null } {
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "analysis") {
    return { name: "analysis" };
  }
  if (parts[0] === "observability") {
    return {
      name: "observability",
      runId: parts[1] ?? null,
    };
  }
  return { name: "explain" };
}
