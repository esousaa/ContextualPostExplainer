import { AlertTriangle, Info } from "lucide-react";

import { Badge } from "../../shared/components/Badge";
import { readableLabel, severityTone } from "./labels";
import type { ValidationWarning } from "./types";

type WarningListProps = {
  warnings: ValidationWarning[];
  compact?: boolean;
};

export function WarningList({ compact = false, warnings }: WarningListProps) {
  if (warnings.length === 0) {
    return null;
  }

  const groupedWarnings = groupWarnings(warnings);

  return (
    <div className={compact ? "warning-list compact" : "warning-list"}>
      {groupedWarnings.map((warning) => {
        const Icon = warning.severity === "info" ? Info : AlertTriangle;
        return (
          <div className="warning-row" key={warning.key}>
            <Icon aria-hidden size={16} />
            <div>
              <Badge tone={severityTone(warning.severity)}>{readableLabel(warning.code.toLowerCase())}</Badge>
              {warning.bulletIndexes.length > 0 && (
                <span className="warning-scope">{formatBulletScope(warning.bulletIndexes)}</span>
              )}
              <p>{warning.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

type GroupedWarning = ValidationWarning & {
  key: string;
  bulletIndexes: number[];
};

function groupWarnings(warnings: ValidationWarning[]): GroupedWarning[] {
  const grouped = new Map<string, GroupedWarning>();

  for (const warning of warnings) {
    const key = `${warning.severity}:${warning.code}:${warning.message}`;
    const existing = grouped.get(key);
    if (existing) {
      if (
        typeof warning.bullet_index === "number" &&
        !existing.bulletIndexes.includes(warning.bullet_index)
      ) {
        existing.bulletIndexes.push(warning.bullet_index);
        existing.bulletIndexes.sort((left, right) => left - right);
      }
      continue;
    }

    grouped.set(key, {
      ...warning,
      key,
      bulletIndexes: typeof warning.bullet_index === "number" ? [warning.bullet_index] : []
    });
  }

  return [...grouped.values()];
}

function formatBulletScope(indexes: number[]) {
  const bulletNumbers = indexes.map((index) => `#${index + 1}`).join(", ");
  return indexes.length === 1 ? `Bullet ${bulletNumbers}` : `Bullets ${bulletNumbers}`;
}
