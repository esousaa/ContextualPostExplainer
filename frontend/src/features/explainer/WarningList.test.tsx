import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WarningList } from "./WarningList";
import type { ValidationWarning } from "./types";

describe("WarningList", () => {
  it("groups identical warning messages and keeps bullet scope visible", () => {
    const warnings: ValidationWarning[] = [
      {
        severity: "warning",
        code: "OFFICIAL_POSITION_WITHOUT_PRIMARY_SOURCE",
        message: "Official position is not supported by an official source.",
        bullet_index: 1
      },
      {
        severity: "warning",
        code: "OFFICIAL_POSITION_WITHOUT_PRIMARY_SOURCE",
        message: "Official position is not supported by an official source.",
        bullet_index: 2
      }
    ];

    render(<WarningList warnings={warnings} />);

    expect(screen.getAllByText("official position without primary source")).toHaveLength(1);
    expect(screen.getByText("Bullets #2, #3")).toBeInTheDocument();
  });
});
