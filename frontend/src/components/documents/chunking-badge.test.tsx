import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChunkingInfo } from "@/lib/api/types";

import { ChunkingBadge } from "./chunking-badge";

function chunking(overrides: Partial<ChunkingInfo>): ChunkingInfo {
  return {
    requested: null,
    strategy: null,
    splitter: null,
    chunk_size: null,
    chunk_overlap: null,
    chunk_count: null,
    total_tokens: null,
    ...overrides,
  };
}

describe("ChunkingBadge", () => {
  it("shows 'Not recorded' when chunking info is null", () => {
    render(<ChunkingBadge chunking={null} />);
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
  });

  it("shows 'Not recorded' when strategy is missing even though an object was passed", () => {
    render(<ChunkingBadge chunking={chunking({ strategy: null, requested: "auto" })} />);
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
  });

  it("shows just the strategy when nothing different was requested", () => {
    render(<ChunkingBadge chunking={chunking({ strategy: "markdown", requested: "markdown" })} />);
    expect(screen.getByText("markdown")).toBeInTheDocument();
  });

  it("shows 'requested → actual' when the requested strategy differs from what ran", () => {
    render(<ChunkingBadge chunking={chunking({ strategy: "markdown", requested: "auto" })} />);
    expect(screen.getByText("auto → markdown")).toBeInTheDocument();
  });

  it("shows just the strategy when nothing was explicitly requested", () => {
    render(<ChunkingBadge chunking={chunking({ strategy: "recursive", requested: null })} />);
    expect(screen.getByText("recursive")).toBeInTheDocument();
  });
});
