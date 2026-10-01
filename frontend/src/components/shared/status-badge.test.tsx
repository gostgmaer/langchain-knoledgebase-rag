import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "./status-badge";

// One distinguishing class per variant (from badge.tsx's own cva definition) — asserting on
// this, not just that the status text renders, actually exercises StatusBadge's status→variant
// mapping rather than just React's ability to render a string.
const DISTINGUISHING_CLASS: Record<string, string> = {
  success: "bg-emerald-100",
  warning: "bg-amber-100",
  destructive: "bg-red-100",
  outline: "border-neutral-200",
  secondary: "bg-neutral-100",
};

describe("StatusBadge", () => {
  it.each([
    ["READY", "success"],
    ["ACTIVE", "success"],
    ["SUCCEEDED", "success"],
    ["COMPLETED", "success"],
    ["PROCESSING", "warning"],
    ["PENDING", "warning"],
    ["QUEUED", "warning"],
    ["RUNNING", "warning"],
    ["FAILED", "destructive"],
    ["DISABLED", "outline"],
    ["ARCHIVED", "outline"],
    ["DEPRECATED", "outline"],
  ])("maps status %s to the %s variant", (status, variant) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(status)).toHaveClass(DISTINGUISHING_CLASS[variant]);
  });

  it("falls back to the secondary variant for an unrecognized status", () => {
    render(<StatusBadge status="SOME_FUTURE_STATUS" />);
    expect(screen.getByText("SOME_FUTURE_STATUS")).toHaveClass(DISTINGUISHING_CLASS.secondary);
  });
});
