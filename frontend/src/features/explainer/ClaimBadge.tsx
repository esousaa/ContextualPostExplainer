import { Badge } from "../../shared/components/Badge";
import { claimTone, readableLabel } from "./labels";
import type { ClaimLabel } from "./types";

type ClaimBadgeProps = {
  value: ClaimLabel;
};

export function ClaimBadge({ value }: ClaimBadgeProps) {
  return <Badge tone={claimTone(value)}>{readableLabel(value)}</Badge>;
}
