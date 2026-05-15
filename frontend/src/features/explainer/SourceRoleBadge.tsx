import { Badge } from "../../shared/components/Badge";
import { readableLabel, sourceCategoryTone } from "./labels";
import type { SourceCategory, SourceRole } from "./types";

type SourceRoleBadgeProps = {
  category: SourceCategory;
  role: SourceRole;
};

export function SourceRoleBadge({ category, role }: SourceRoleBadgeProps) {
  return (
    <span className="source-role-badges">
      <Badge tone={sourceCategoryTone(category)}>{readableLabel(category)}</Badge>
      <Badge tone="neutral">{readableLabel(role)}</Badge>
    </span>
  );
}
